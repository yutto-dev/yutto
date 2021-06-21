# yutto 贡献快速指南

很高兴你对参与 yutto 的贡献感兴趣，在提交你的贡献之前，请花一点点时间阅读本指南

## 工具安装

为了获得最佳的开发体验，希望你能够安装一些开发工具

### 依赖管理工具 poetry

[poetry](https://github.com/python-poetry/poetry) 是 yutto 用来进行依赖管理的工具，通过 pip 就可以很方便地安装它：

```bash
pip install poetry
```

### 命令执行工具 just

[just](https://github.com/casey/just) 是一款用 rust 编写的简单易用的命令执行工具，通过它可以方便地执行一些开发时常用的命令。安装方法请参考[它的文档](https://github.com/casey/just#installation)

### 编辑器 Visual Studio Code

[VSCode](https://github.com/microsoft/vscode) 是一款功能强大的编辑器，由于 yutto 全面使用了 [Type Hints](https://docs.python.org/3/library/typing.html)，所以这里建议使用 VSCode + 扩展 pylance 来保证类型提示的准确性，同时配置格式化工具 black 以保证代码格式的一致性。

当然，如果你有更熟悉的编辑器或 IDE 的话，也是完全可以的。

## 本地调试

如果你想要本地调试，最佳的方案是从 github 上下载最新的源码来运行

```bash
git clone git@github.com:SigureMo/yutto.git
cd yutto/
poetry install
poetry run yutto -v
```

注意本地调试请不要直接使用 `yutto` 命令，那只会运行使用从 pip 安装的 yutto，而不是本地调试的 yutto。

## 模块结构

> TODO: 说明各个模块的作用

## 测试

yutto 已经编写好了一些测试，请确保在改动后仍能通过测试

```bash
just test
```

当然，如果你修改的内容需要对测试用例进行修改和增加，请尽管修改。

## 代码格式化

yutto 使用 black 对代码进行格式化，如果你的编辑器或 IDE 没有自动使用 black 进行格式化，请使用下面的命令对代码进行格式化

```bash
just fmt
```

## 提交 PR

提交 PR 的最佳实践是 fork 一个新的 repo 到你的账户下，并创建一个新的分支，在该分支下进行改动后提交到 GitHub 上，并发起 PR（请注意在发起 PR 时不要取消掉默认已经勾选的 `Allow edits from maintainers` 选项）

```bash
# 首先在 GitHub 上 fork
git clone git@github.com:<YOUR_USER_NAME>/yutto.git         # 将你的 repo clone 到本地
cd yutto/                                                   # cd 到该目录
git remote add upstream git@github.com:SigureMo/yutto.git   # 将原分支绑定在 upstream
git checkout -b <NEW_BRANCH>                                # 新建一个分支，名称随意，最好含有你本次改动的语义
git push origin <NEW_BRANCH>                                # 将该分支推送到 origin （也就是你 fork 后的 repo）
# 对源码进行修改、并通过测试
# 此时可以在 GitHub 发起 PR
```

如果你的贡献需要继续修改，直接继续向该分支提交新的 commit 即可，并推送到 GitHub，PR 也会随之更新

如果你的 PR 已经被合并，就可以放心地删除这个分支了

```bash
git checkout main                                           # 切换到 main
git fetch upstream                                          # 将原作者分支下载到本地
git merge upstream/main                                     # 将原作者 main 分支最新内容合并到本地 main
git branch -d <NEW_BRANCH>                                  # 删除本地分支
git push origin --delete <NEW_BRANCH>                       # 同时删除远程分支
```

## PR 规范

### 标题

表明你所作的更改即可，没有太过苛刻的格式（合并时会重命名）

如果可能，可以按照 `<gitmoji> <type>: <subject>` 来进行命名

### 内容

尽可能按照模板书写

**因为有你，yutto 才会更加完善，感谢你的贡献**
