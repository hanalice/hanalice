---
title: 使用ssh-agent 管理多个ssh key
date: 2017-08-07
tags: SSH, Git, Agent
---

```
举例当前用户为test_1 和 hanalice
```

### 查看代理
```
ssh-add -l
如果出现以下结果，说明系统代理里面没有任何key
view plain copy
Could not open a connection to your authentication agent.
执行如下操作：
exec ssh-agent bash
如果系统已经有ssh-key 代理，可以直接删除
ssh-add -D
```

### 添加私钥
```
ssh-add ~/.ssh/id_rsa  
ssh-add ~/.ssh/id_rsa_github
```

### 添加公钥
```
在对应的gitlab和github的ssh管理页面，添加对应的公钥（.pub 文件内容），保存到代码管理服务器。
```

### 编辑或者添加~/.ssh/config 文件
```
# github
Host github.com
    HostName github.com
    PreferredAuthentications publickey
    IdentityFile ~/.ssh/id_rsa_github
    user hanalice

# gitlab
Host gitlab.com
    HostName gitlab.com
    PreferredAuthentications publickey
    IdentityFile ~/.ssh/id_rsa
    user test_1
```

### 验证repository是否通过权限验证
```
ssh -T git@github.com
如果出现以下结果，表明成功
Hi XXX! You've successfully authenticated, but GitHub does not provide shell access.  
如果出现以下结果，请检查github的ssh管理里添加的公钥是否正确
permission denied (publickey)
```
