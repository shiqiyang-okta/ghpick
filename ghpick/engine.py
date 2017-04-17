import re
import json
import logging
import requests

try:
    requests.packages.urllib3.disable_warnings()
except AttributeError:
    # Some versions of urllib3 give us difficulty
    pass

logging.captureWarnings(True)

from base64 import b64encode, b64decode

class GithubBadRequest(Exception):
    """ 400 Bad Request.

    Happens when the JSON couldn't be parsed.
    """
    pass

class GithubUnprocessableEntity(Exception):
    """ 422 Unprocessable Entity """
    pass

class GithubInvalidCredentials(Exception):
    """ 401 Unauthorized """
    pass

class GithubMergeConflict(Exception):
    """ 409 Conflict """
    pass

class GithubNotFound(Exception):
    """ 404 Not Found """
    pass

class GithubGeneralException(Exception):
    """ Everything Else """
    pass

class GitInvalidSha(Exception):
    """ Represents an invalid sha """
    pass

class GithubRequestsEngine(object):
    """ Perform the requests to Github

    This is the engine that performs the requests to Github.
    """

    HTTP_EXCEPTIONS = {
        400: GithubBadRequest,
        401: GithubInvalidCredentials,
        409: GithubMergeConflict,
        404: GithubNotFound,
        422: GithubUnprocessableEntity,
        500: GithubGeneralException
    }

    def __init__(self, username, password, org, repo, base_url=None):
        self.username = username
        self.password = password
        self.org = org
        self.repo = repo

        base_url = base_url or "https://api.github.com"
        self.base_url = "{}/repos/{}/{}".format(base_url, org, repo)

        # Endpoints
        self.diff_media_type = "application/vnd.github.3.diff"
        self.patch_media_type = "application/vnd.github.3.patch"
        self.contents_url = "{}/contents".format(self.base_url)
        self.merge_url = "{}/merges".format(self.base_url)
        self.compare_url = "{}/compare".format(self.base_url)
        self.trees_url = "{}/git/trees".format(self.base_url)
        self.refs_url = "{}/git/refs".format(self.base_url)
        self.blobs_url = "{}/git/blobs".format(self.base_url)
        self.commits_url = "{}/git/commits".format(self.base_url)
        self.repo_commits_url = "{}/commits".format(self.base_url)

    @staticmethod
    def is_valid_sha(sha):
        """ Validates the SHA matches a regex """
        res = None

        if isinstance(sha, basestring):
            res = re.match("^[a-fA-F0-9]{40,40}$", sha)
        if res:
            return True
        else:
            return False

    def _make_payload(self, data):
        """ Make the json payload from a dict """
        payload = None
        if isinstance(data, dict):
            payload = json.dumps(data)
        else:
            payload = data
        return payload        

    def _validate_response(self, response):
        """ Utility to validate response status code """
        code = response.status_code

        if code not in self.HTTP_EXCEPTIONS:
            return True

        logging.debug("Status code in Exceptions: {}".format(code))
        exc = self.HTTP_EXCEPTIONS[code]
        logging.debug("Raising %s" % exc)
        
        request = response.request
        logging.error("METHOD: {}".format(request.method))
        logging.error("URL: {}".format(request.url))
        logging.error("BODY: {}".format(request.body))
        raise exc("Message: {}".format(response.text))

    ###### HTTP REQUESTS ######
    def _get(self, url, query_parameters=None, media_type=None):
        """ Abstract the requests.get call """
        headers = dict()
        if media_type:
            headers['Accept'] = media_type

        response = requests.get(url, 
            params=query_parameters,
            auth=(self.username, self.password),
            headers=headers,
            verify=False)

        self._validate_response(response)

        try:
            item = response.json()
        except:
            item = response.text

        return item

    def _patch(self, url, data=None):
        """ Abstract the requests.patch call """
        payload = self._make_payload(data)

        response = requests.patch(url,
            data=payload,
            auth=(self.username, self.password),
            verify=False)
        self._validate_response(response)
        item = response.json()

        return item

    def _post(self, url, data=None):
        """ Abstract the requests.post call """
        payload = self._make_payload(data)

        logging.debug("POST %s" % url)
        logging.debug("PAYLOAD: %s" % payload)
        response = requests.post(url,
            data=payload,
            auth=(self.username, self.password),
            verify=False)

        self._validate_response(response)
        item = response.json()

        return item
    ######

    def create_blob(self, contents):
        """ Creates a blob

        Params:
            contents (string): The contents to write to the file.

        Returns:
            https://developer.github.com/v3/git/blobs/#response-1
        """
        payload = dict(content=b64encode(contents), encoding="base64")
        return self._post(self.blobs_url, data=payload)

    def get_blob(self, sha):
        """ Retrieve a blob by SHA

        Params:
            sha (string): The blob SHA

        Returns:
            https://developer.github.com/v3/git/blobs/#get-a-blob
        """
        url = '/'.join((self.blobs_url, sha))
        return self._get(url)

    def get_tree(self, sha, recursive=False):
        """ Get the tree pointed at by the tree sha

        Note that this SHA is not the commit sha, but the tree
        SHA which a commit points to.

        This is a github only method.

        Returns:
            https://developer.github.com/v3/git/trees/#get-a-tree
        """
        sha = self.get_sha(sha)
        url = '/'.join((self.trees_url, sha))

        query_parameters = None
        if recursive:
            query_parameters = dict(recursive=True)

        return self._get(url, query_parameters=query_parameters)

    def create_tree(self, tree):
        """ Create the given tree

        Creates the tree defined by the `tree` struct. See:
        https://developer.github.com/v3/git/trees/#create-a-tree
        for the structure necessary.

        Note that if you create a tree, and there's no `base_tree` element
        then that tree is effectively a clobber. This is how you delete files,
        by simply leaving them out of the tree.

        When you use a `base_tree` parameter in the tree then it will just
        update that tree, meaning adding new files or updating files to the
        new sha.  Anything left out will just be untouched.

        Returns the tree from github. See:
        https://developer.github.com/v3/git/trees/#create-a-tree
        """
        new_tree = self._post(self.trees_url, data=tree)
        return new_tree

    def point_branch(self, branch, commit_sha):
        """ Update a branch to point at the commit sha 

        Params:
            branch (string): The name of the branch
            commit_sha (string): The commit SHA to point the branch at

        Returns:
            https://developer.github.com/v3/git/refs/#response-2
        """
        sha = self.get_sha(commit_sha)
        url = '/'.join((self.refs_url, 'heads', branch))
        payload = dict(sha=commit_sha)
        return self._patch(url, data=payload)

    def get_ref(self, namespace, name):
        """ Returns a ref

        Args:
            namespace (string): heads or tags
            name (string): The name of the ref to retrieve

        Returns:
            The dictified JSON response
            https://developer.github.com/v3/git/refs/#response
        """
        url = '/'.join((self.refs_url, namespace, name))
        return self._get(url)

    def get_sha(self, item):
        """ Returns the sha for sha, branch, or tag

        This will take an item, whether it's a SHA-1 string,
        branch name, or a tag, and return the SHA-1.

        Args:
            item (string): The unknown

        Returns:
            sha, raises InvalidSha if none found
        """
        # If they passed in a sha let's get it over with
        if self.is_valid_sha(item):
            return item

        # Both methods raise exceptions. This is better.
        for method in (self.get_branch, self.get_tag):
            try:
                return method(item)['object']['sha']
            except:
                pass
        raise GitInvalidSha("{} could not be converted to a SHA-1".format(item))

    def get_file(self, path, commit_sha):
        """ Retrieves the file

        Args:
            path (string): The path to the file`
            commit_sha (string): The sha, branch, or tag to retrieve the file from

        Returns:
            The contents struct defined at:
            https://developer.github.com/v3/repos/contents/#get-contents
        """
        sha = self.get_sha(commit_sha)
        url = '/'.join((self.contents_url, path))
        fetched = self._get(url, query_parameters=dict(ref=sha))
        fetched['content'] = b64decode(fetched['content'])
        return fetched

    def get_tag(self, tag):
        """ Retrieves a lightweight tag

        Args:
            tag (string): The full name of the tag

        Returns:
            The dictified JSON response
            https://developer.github.com/v3/git/refs/#response

            If there are multiple tags (if you gave only part of
            the path) then the response will be an array of dicts.
        """
        return self.get_ref('tags', tag)

    def get_branch(self, branch):
        """ Retrieve a branch

        Args:
            branch (string): The name of the branch minus refs/heads

        Returns:
            The dictified JSON response
            https://developer.github.com/v3/git/refs/#response
        """
        return self.get_ref('heads', branch)

    def get_commit(self, sha):
        """ Returns a single commit

        Args:
            sha (string): The sha, tag, or branch name

        Returns:
            The dictified JSON response
            https://developer.github.com/v3/repos/commits/#get-a-single-commit
        """
        sha = self.get_sha(sha)
        url = '/'.join((self.commits_url, sha))
        return self._get(url)

    def create_commit(self, message, tree_sha, parents, author_info):
        """ Creates a commit

        Creates a commit that points to the given tree.

        Args:
            message (string): The message
            tree_sha (string): The sha of the tree to point at
            parents (list): An array of parent commit sha's

        Returns:
            https://developer.github.com/v3/git/commits/#create-a-commit
        """
        payload = dict(message=message,
            tree=tree_sha,
            author=author_info,
            parents=parents)
        return self._post(self.commits_url, data=payload)

    def commits(self, starting_sha, ending_sha):
        """ Returns the list of commits between two shas.

        Returns a list of commits between the starting_sha and
        the destination sha.

        Args:
            starting_sha (string): The sha or tag or branch tip to start from
            destination_sha (string): The sha, tag, or branch to search until

        Returns:
            A tuple of commit objects.
            See https://developer.github.com/v3/git/commits/#get-a-commit
        """
        starting_sha = self.get_sha(starting_sha)
        ending_sha = self.get_sha(ending_sha)

        starting_commit = self.get_commit(starting_sha)
        starting_time = starting_commit['committer']['date']

        commit_list = self._get(self.repo_commits_url, query_parameters=dict(
            sha=ending_sha,
            since=starting_time))

        pared_commit_list = list()
        for commit in commit_list:
            if commit['sha'] == starting_commit['sha']:
                break
            pared_commit_list.append(commit)
        return pared_commit_list
    
    def compare(self, base_sha, destination_sha, as_diff=False, as_patch=False):
        """ Compares two commits

        Compare two commits and return a structure defined at
        https://developer.github.com/v3/repos/commits/#compare-two-commits
        """
        base_sha = self.get_sha(base_sha)
        destination_sha = self.get_sha(destination_sha)
        compare_string = '...'.join((base_sha, destination_sha))
        url = '/'.join((self.compare_url, compare_string))

        media_type = None
        if as_diff:
            media_type = self.diff_media_type
        elif as_patch:
            media_type = self.patch_media_type

        return self._get(url, media_type=media_type)


