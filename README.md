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
      userame='ima_user',
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
        base_sha='7a23...',
        target_sha='82aa1...',
        target_branch='integration_branch_1')
  except GithubMergeConflict as e:
    send_email(to=developer, message="Conflicts: {}".format(e))
  else:
    commit = cherry.commit()
    print "Commit SHA: {}".format(commit['sha'])
```
Those SHAs you pass in to the patch method can be tags, complete SHAs, or a branch name. If you choose a branch name then it will resolve to the HEAD of that branch.

### Installation
```Shell
  git clone https://github.com/whiskeyriver/ghpick
  cd ghpick
  python setup.py install
```
I'll have a pip package up at some point.

### Requirements
* git must be installed. The command used to patch the files is "git apply"

### Todo
The tests need to be rewritten. Sorry about that, I had a tight deadline.

### Warnings
As always, use this library at your own risk. Plese test this in your environment before letting it run free since this rebuilds the tree. Luckily you can revert if you have to.

### Please
Please file issues if you need, or feel free to email me with any questions. Pull requests certainly welcome, though I don't imagine I'll get those without fixing those tests :)
