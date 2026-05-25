---
title: Git修改历史提交的作者信息
date: 2024-09-19
tags: Git
---

1. config git username and email globally, otherwise omit --global to config in current repo.

```bash
$ git config --global user.name "new name"
$ git config --global user.email "new email"
```

2. execute below command in git bash to batch update author information

```bash
$ git filter-branch --env-filter '
    OLD_EMAIL="Old email"
    CORRECT_NAME="new username"
    CORRECT_EMAIL="new email"
    if [ "$GIT_COMMITTER_EMAIL" = "$OLD_EMAIL" ]
    then
        export GIT_COMMITTER_NAME="$CORRECT_NAME"
        export GIT_COMMITTER_EMAIL="$CORRECT_EMAIL"
    fi
    if [ "$GIT_AUTHOR_EMAIL" = "$OLD_EMAIL" ]
    then
        export GIT_AUTHOR_NAME="$CORRECT_NAME"
        export GIT_AUTHOR_EMAIL="$CORRECT_EMAIL"
    fi
    ' --tag-name-filter cat -- --branches --tags
```

3. check the result using `git log` command
