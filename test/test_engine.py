import unittest

from ghpick.engine import GithubRequestsEngine
from ghpick.engine import GithubInvalidCredentials
from ghpick_vcr import gvcr

from base64 import b64encode, b64decode

class TestEngine(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.engine = GithubRequestsEngine(
            username='test',
            password='test',
            org='whiskeyriver',
            repo='ghpick_test')

    def is_valid_sha(self):
        sha = 'edd616831af5425cbee99db4ca711c89223bd6c2'
        is_valid = self.engine.is_valid_sha(sha)
        self.assertTrue(is_valid)

    def is_invalid_sha(self):
        sha = 'invalid_sha'
        is_valid = self.engine.is_valid_sha(sha)
        self.assertFalse(is_valid)

    @gvcr.use_cassette()
    def test_invalid_credentials(self):
        with self.assertRaises(GithubInvalidCredentials):
            self.engine.get_branch('invalid_creds')

    @gvcr.use_cassette()
    def test_make_blob(self):
        content = 'This is a blob'
        blob = self.engine.create_blob(content)
        ret_blob = self.engine.get_blob(blob['sha'])
        b64content = b64encode(content)
        self.assertEqual(ret_blob['content'].strip(), b64content)

    @gvcr.use_cassette()
    def test_get_blob(self):
        blob = self.engine.get_blob('7ad71a06ce2c995f4c7d61a6f0f1ed3edca66e8f')
        content = b64decode(blob['content'])
        self.assertEqual(content, 'This is a blob')

    @gvcr.use_cassette()
    def test_get_tree(self):
        tree = self.engine.get_tree('d2639b648021bee4e8ef46306e4117e9bde1d17c')
        self.assertEqual(tree['sha'], 'd2639b648021bee4e8ef46306e4117e9bde1d17c')
        self.assertEqual(tree['tree'][0]['sha'], 'a5f10b9fb3f35339d9d50133fa95343283ee11f3')

    @gvcr.use_cassette()
    def test_create_tree(self):
        tree = dict(
            tree=[dict(
                path="README_RENAMED.md",
                mode="100644",
                type="blob",
                sha="a5f10b9fb3f35339d9d50133fa95343283ee11f3"
            )]
        )

        ret_tree = self.engine.create_tree(tree)
        self.assertEqual(ret_tree['sha'], '4411d83cb603091d6c3bf4607befc6b2c4e3099b')

    @gvcr.use_cassette()
    def test_get_commit(self):
        commit = self.engine.get_commit('dbf4eb1e4eada9ebfd6f4e587456d51d7d569364')
        self.assertEqual(commit['sha'], 'dbf4eb1e4eada9ebfd6f4e587456d51d7d569364')

    @gvcr.use_cassette()
    def test_create_commit(self):
        commit = self.engine.create_commit(
            message='test',
            tree_sha='4411d83cb603091d6c3bf4607befc6b2c4e3099b',
            parents=['dbf4eb1e4eada9ebfd6f4e587456d51d7d569364'])
        self.assertEqual(commit['sha'],'0dc54282f1a68c5bf9c455df85d7d627decf0fc2')

    @gvcr.use_cassette()
    def test_point_branch(self):
        ref = self.engine.point_branch('master', '0dc54282f1a68c5bf9c455df85d7d627decf0fc2')
        self.assertEqual(ref['ref'],'refs/heads/master')
        self.assertEqual(ref['object']['sha'], '0dc54282f1a68c5bf9c455df85d7d627decf0fc2')

    @gvcr.use_cassette()
    def test_get_sha(self):
        sha = self.engine.get_sha('master')
        self.assertEqual(sha, '0dc54282f1a68c5bf9c455df85d7d627decf0fc2')

