# ghpick
Github Cherry Picker

Create and commit cherry-pick patches over the Github API

### Why
I had a need. I needed to perform cherry-pick patch deliveries without having a working copy. The Github API is fantastic and feature rich, but this is probably a feature they ought not support.

### How
```Python
  from ghpick.cherry import CherryPick
  from ghpick.engine import GithubMergeConflict
  
  ## For standard users:
  cherry = CherryPick(
      username='ima_user',
      password='ima_pass',
      org='ima_user',
      repo='ghpick')
  ## For enterprise users:
  cherry = CherryPick(
      username='ima_user',
      password='ima_pass',
      org='MyTeam',
      repo='MyRepo',
      base_url='https://github.mycompany.com/api/v3')
  try:
    cherry.patch(
        base_sha='7a23...full-sha',
        target_sha='82aa1...full-sha',
        target_branch='integration_branch_1')
  except GithubMergeConflict as e:
    send_email(to=developer, message="Conflicts: {}".format(e))
  else:
    commit = cherry.commit()
    print "Commit SHA: {}".format(commit['sha'])
```
Those SHAs you pass in to the patch method can be tags, complete SHAs, or a branch name. If you choose a branch name then it will resolve to the HEAD of that branch.

If you don't pass "message" to the commit method a reasonable default is chosen. You could take advantage of the commits method in the engine to get the list of commits in a range and create a comprehensive message:

```Python

  commits = cherry.engine.commits('7a2b...full-sha','822b...full-sha')
  message = '\n\n'.join([ c['commit']['message'] for c in commits ])
  cherry.commit(message=message)
```

### Installation
```Shell
  pip install ghpick
```

### Requirements
* git must be installed. The command used to patch the files is "git apply"

### Todo
The tests need to be rewritten. 

### Warnings
As always, use this library at your own risk. Plese test this in your environment before letting it run free since this rebuilds the tree. You can always revert if something goes wrong.

### Please
Please file issues if you need, or feel free to email me with any questions. Pull requests are welcome.
