import os

import unittest
import filecmp

from ghpick.cherry import CherryPick
from ghpick_vcr import gvcr

from pprint import pprint as pp

class TestCherryPick(unittest.TestCase):
    patch_dir = os.path.join(
        os.path.dirname(__file__),
        '..',
        'fixtures',
        'patched_files')

    def setUp(self):
        self.cherry = CherryPick(
            username='test',
            password='test',
            org='whiskeyriver',
            repo='ghpick_test')

    def tearDown(self): 
        if os.path.isdir(self.cherry.cwd):
            self.cherry._delete_workspace()
        pass

    def test_prepare_workspace(self):
        self.cherry._prepare_workspace()
        self.assertTrue(os.path.isdir(self.cherry.cwd))
        self.assertTrue(os.path.isdir(self.cherry.files_base))

    @gvcr.use_cassette()
    def test_make_patch(self):
        self.cherry._prepare_workspace()
        self.cherry._make_patch('11130ef268026d7a895c01825db34804e2b98df6','27a222596d26ce4097a1d42b1b449505d3d192a2')
        self.assertEqual(self.cherry.patch_summary, self.patch_summary())
    
    @gvcr.use_cassette()
    def test_fetch_files(self):
        self.cherry.target_branch = 'test_branch'
        self.cherry._prepare_workspace()
        self.cherry._make_patch('0dc54282f1a68c5bf9c455df85d7d627decf0fc2','27a222596d26ce4097a1d42b1b449505d3d192a2')
        self.cherry._fetch_files()

        readme = os.path.join(self.cherry.files_base, 'README.md')
        newfile = os.path.join(self.cherry.files_base, 'NewFile.txt')
        self.assertTrue(os.path.isfile(readme))
        self.assertFalse(os.path.isfile(newfile))

    @gvcr.use_cassette()
    def test_patch(self):
        retval = self.cherry.patch(
            base_sha='7bee46915e2a29ac789ac18b43dcdb438377bfbd', 
            target_sha='b23e9fd3a3518faf703d9cc90c3cafb079e4488d',
            target_branch='test_branch')
        self.assertTrue(retval)

        (match, mismatch, errors) = filecmp.cmpfiles(
            self.cherry.files_base, 
            self.patch_dir,
            ['README.md'])

        self.assertEqual(len(match), 1)
        self.assertEqual(len(mismatch), 0)
        self.assertEqual(len(errors), 0)

    @gvcr.use_cassette()
    def test_commit(self):
        retval = self.cherry.patch(
            base_sha='before_test_commit', 
            target_sha='test_commit',
            target_branch='test_branch')
        self.assertTrue(retval)

        commit = self.cherry.commit()
        target_branch_sha = self.cherry.engine.get_sha('test_branch')
        self.assertEqual(commit['sha'], target_branch_sha)

    @gvcr.use_cassette()
    def test_deletion(self):
        retval = self.cherry.patch(
            base_sha='27a222596d26ce4097a1d42b1b449505d3d192a2',
            target_sha='955a169733c3199f606d6a9157b22a85521a407f',
            target_branch='test_branch')
        self.assertTrue(retval)

        commit = self.cherry.commit()
        tree = self.cherry.engine.get_tree(commit['tree']['sha'])

        self.assertEqual(len(tree['tree']), 1)
        self.assertEqual(tree['tree'][0]['path'], 'README.md')

    @gvcr.use_cassette()
    def test_nested_actions(self):
        retval = self.cherry.patch(
            base_sha='88367985976a838381943611803f1e938d30c763',
            target_sha='d0448fd31e341842e7fa2ca76acd5dfed3366c73',
            target_branch='test_branch')
        self.assertTrue(retval)

        commit = self.cherry.commit()
        tree = self.cherry.engine.get_tree(commit['tree']['sha'], recursive=True)

        good_paths = ('README.md','file_addition.txt','test','test/nested',
                      'test/nested/mods','test/nested/mods/and',
                      'test/nested/mods/and/deletions',
                      'test/nested/mods/and/deletions/mod_me.txt')
        for item in tree['tree']:
            self.assertIn(item['path'], good_paths)


    def patch_summary(self):
        return [
            {
                'is_deleted': False, 
                'mode': None, 
                'path': 'README.md'
            },
            {
                'is_deleted': False, 
                'mode': '100644', 
                'path': 'NewFile.txt'
            }
        ]
