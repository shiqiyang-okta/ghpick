import os
import re
import copy
import logging
import tempfile

import sh
import shutil
import distutils.dir_util

from .engine import GithubRequestsEngine, GithubMergeConflict, GithubNotFound

class CherryPick(object):
    """ CherryPick

    Use CherryPick to apply the differences between two SHAs to a target branch.

    Usage:
        cherry = CherryPick(username=username, password=password,
                            org=organization, repo=repo)
        cherry.patch(base_sha=sha1, target_sha=sha2, target_branch='rel_1.0_dev')
        cherry.commit()

    For enterprise users:
        You'll need to pass the full URL to your Github instance to the
        constructor.

        i.e.:
        cherry = CherryPick(username=username, password=password,
                            org=organization, repo=repo,
                            base_url='https://gh.internal.com/api/v3')

    When committing:
        If you don't pass a commit message then a default will be used:
        "This is a cherry pick between {sha1} and {sha2}."

        If you would like a more thorough commit message you could, for example,
        retrieve the list of commits between the two shas via the 
        GithubRequestsEngine.commits method and include each SHA plus message.
    """
    default_dir_mode = '040000'
    default_file_mode = '100644'

    def __init__(self, username, password, org, repo, base_url=None):
        """ CherryPick

        Params:
            username (string): The username
            password (string): The password
            org (string): The Github org (could be the username)
            repo (string): The repo
            base_url (string): The full URL for Enterprise.
        """
        self.engine = GithubRequestsEngine(
            username=username,
            password=password,
            org=org,
            repo=repo,
            base_url=base_url)

    def patch(self, base_sha, target_sha, target_branch):
        """ Apply the patch

        This will create a temporary directory under $TMPDIR, retrieve
        the files from `target_branch`, and apply the patch using
        `git apply`.

        Params:
            base_sha (string): The base sha
            target_sha (string): The target sha
            target_branch (string): The branch to make the changes to

        Returns:
            True if successful. Otherwise an exception will be raised.
        """
        self.base_sha = base_sha
        self.target_sha = target_sha
        self.target_branch = target_branch
        self._prepare_workspace()
        self._make_patch(base_sha, target_sha)
        self._fetch_files()
        return self._apply_patch()

    def commit(self, message=None):
        message = message or \
            "This is a cherry-pick between {} and {}". \
            format(self.base_sha, self.target_sha)
        target_tree = self.engine.get_tree(self.target_branch)
        tree = self._build_tree(target_tree)

        parent_commit = self.engine.get_commit(self.target_branch)
        commit = self.engine.create_commit(message,
                                           tree['sha'],
                                           [parent_commit['sha']])

        self._delete_workspace()
        self.engine.point_branch(self.target_branch, commit['sha'])
        return commit

    def _make_patch(self, base_sha, target_sha):
        """ Retrieves the patch file and sends it to the parsers """
        self.patchdata = self.engine.compare(base_sha, target_sha, as_patch=True)
        self.patchfile = os.path.join(self.cwd, "patch")
        with open(self.patchfile, 'w') as patch:
            patch.write(self.patchdata)
        self._make_patch_summary()
        self._build_patch_tree()
        
    def _apply_patch(self):
        """ Executes the patch command """
        output = []
        try:
            sh.git('apply',
                   self.patchfile,
                   verbose=True,
                   reject=True,
                   directory=self.files_base,
                   _out=lambda a: output.append(a),
                   _err=lambda a: output.append(a))
        except sh.ErrorReturnCode as e:
            exc = GithubMergeConflict('\n'.join(output))
            raise exc

        # If the only change is deletion git will delete the b
        # directory. We have to recreate it empty to build the tree
        if not os.path.isdir(self.files_base):
            os.mkdir(self.files_base)

        return True

    def _prepare_workspace(self):
        """ Creates the required directory structure """
        prefix = '_'.join((self.__class__.__name__, "wd"))
        self.cwd = tempfile.mkdtemp(prefix=prefix)
        self.files_base = os.path.join(self.cwd, 'b')
        os.mkdir(self.files_base)
    
    def _fetch_files(self):
        """ Download each file to patch """

        # First we create the tree to put the files into
        files = [ x['path'] for x in self.patch_summary ]
        distutils.dir_util.create_tree(self.files_base, files)

        for item in self.patch_summary:
            try:
                fetched = self.engine.get_file(item['path'], self.target_branch)
                content = fetched['content']
            except GithubNotFound:
                # If the file has been deleted from the source then
                # it won't exist and we can skip. If it's a new file
                # then it won't exist and will be created by the patch
                continue

            path = os.path.join(self.files_base, item['path'])

            with open(path, 'w') as f:
                f.write(content)

    def _delete_workspace(self):
        """ Deletes the workspace """
        shutil.rmtree(self.cwd, ignore_errors=True)

    def _make_patch_summary(self):
        """ Parse the git 'am' style patch file

        Returns:
            A list of dictionaries representing each file. The
            dictionary will have the following keys:
             - path
             - mode
             - is_deleted
        """
        header_start_re = re.compile(r'^diff --git a/(.*?) b/.*$')
        new_mode_re = re.compile(r'^new (?:file ){0,1}mode (\d+)$')
        deleted_file_re = re.compile(r'deleted file mode (\d+)')
        terminator_re = re.compile(r'^(?:index|\+\+\+|---)')

        patch_summary = []
        with open(self.patchfile, 'r') as f:
            curr_file = None
            curr_mode = None
            curr_deleted = False

            for line in f:
                if not curr_file:
                    match = header_start_re.match(line)
                    if match:
                        curr_file = match.group(1)
                else:
                    match = new_mode_re.match(line)
                    if match:
                        curr_mode = match.group(1)

                    match = deleted_file_re.match(line)
                    if match:
                        curr_deleted = True

                    match = terminator_re.match(line)
                    if match:
                        obj = dict(path=curr_file,
                                   mode=curr_mode,
                                   is_deleted=curr_deleted)
                        patch_summary.append(obj)
                        curr_file, curr_mode, curr_deleted = None, None, False

            # In some cases the patch file will end without a terminator_re
            if curr_file:
                obj = dict(path=curr_file,
                           mode=curr_mode,
                           is_deleted=curr_deleted)
                patch_summary.append(obj)

        self.patch_summary = patch_summary

    def _build_patch_tree(self):
        """ Create a nested dict representing the patch """
        patch_tree = dict()
        for item in self.patch_summary:
            path = item['path']
            elems = [ x for x in path.split(os.sep) if x != '' ]
            retdict = self._build_patch_tree_path(item, elems)
            patch_tree = self._dict_merge(patch_tree, retdict)
        self.patch_tree = patch_tree

    def _build_patch_tree_path(self, item, elems):
        """ Recursive method for building the patch dict """
        key = elems.pop(0)
        if len(elems) == 0:
            return { key: item }
        return { key: self._build_patch_tree_path(item, elems) }

    def _dict_merge(self, a, b):
        """ Merge dictionaries recursively """
        if not isinstance(b, dict):
            return b
        result = copy.deepcopy(a)
        for k, v in b.iteritems():
            if k in result and isinstance(result[k], dict):
                    result[k] = self._dict_merge(result[k], v)
            else:
                result[k] = copy.deepcopy(v)
        return result

    def _build_tree(self, tree):
        """ Head of the recursion for building out the git tree object """
        if 'patch_tree' not in self.__dict__:
            self._build_patch_tree()

        new_tree = self._build_tree_recurse(self.patch_tree, tree)
        return self.engine.create_tree(new_tree)

    def _build_tree_recurse(self, hash_entry, tree):
        """ The recursive workhorse that builds the tree """
        tree_entries = { x['path']: x for x in tree['tree'] }
        for k,v in hash_entry.iteritems():
            if 'path' in v and isinstance(v['path'], str):
                # We're a file

                # For mode changes and new files we want to make
                # sure to take our defaults from the patch entry
                tree_entry = dict(
                    path=k,
                    mode=v.get('mode', self.default_file_mode))

                entry = self._make_blob(v, tree_entry)
            else:
                # We're a tree
                if k in tree_entries:
                    next_tree = self.engine.get_tree(tree_entries[k]['sha'])
                else:
                    next_tree = dict(tree=[])

                # For new directories we make sure we take from the
                # patch entry
                tree_entry = dict(
                    path=k,
                    mode=v.get('mode', self.default_dir_mode))

                new_tree = self._build_tree_recurse(v, next_tree)
                entry = self._make_tree(v, tree_entry, new_tree)

            if entry is None:
                tree_entries.pop(k, None)
            else:
                tree_entries[k] = entry

        if len(tree_entries.keys()) == 0:
            return None
        else:
            return dict(tree=tree_entries.values())

    def _make_blob(self, entry, tree_entry):
        """ Creates a blob out of the filepath and returns it """
        # If we're deleted just return None
        if entry['is_deleted']:
            return None

        contents = None
        filepath = entry['path']
        if os.path.isabs(filepath):
            abspath = filepath
        else:
            abspath = os.path.join(self.files_base, filepath)
        with open(abspath, 'rb') as f:
            contents = f.read()

        blob = self.engine.create_blob(contents)
        return dict(
            path=tree_entry['path'],
            mode=tree_entry['mode'] or self.default_file_mode,
            sha=blob['sha'],
            type='blob')

    def _make_tree(self, entry, tree_entry, new_tree):
        """ Create the new tree """
        if new_tree is None:
            return None

        ret_tree = self.engine.create_tree(new_tree)
        return dict(
            path=tree_entry['path'],
            mode=tree_entry['mode'] or self.default_dir_mode,
            sha=ret_tree['sha'],
            type='tree')

