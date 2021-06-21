# yutto 贡献快速指南

<!-- 暂时直接 copy bilili 的，后续需针对 yutto 优化细节 -->

很高兴你对参与 yutto 的贡献感兴趣，在提交你的贡献之前，请花一点点时间阅读本指南

> TODO: justfile 相关
> TODO: poetry 相关
> TODO: 说明各个模块的作用

## 本地调试

如果你想要本地调试，最佳的方案是从 github 上下载最新的源码来运行

```bash
git clone git@github.com:SigureMo/yutto.git
cd yutto/
pip install -r requirements.txt
python -m yutto get <url>
```

注意本地调试请不要直接使用 `yutto` 命令

## 开发环境建议

由于 yutto 全面使用了 [Type Hints](https://docs.python.org/3/library/typing.html)，所以这里建议使用 VSCode + 扩展 pylance 来保证类型提示的准确性，同时配置格式化工具 black 以保证代码格式的一致性。

## 测试

> TODO

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

表明你所作的更改即可，没有太过苛刻的格式

如果可能，可以按照 `<gitmoji> <type>: <subject>` 来进行命名

### 内容

尽可能按照模板书写

**因为有你，yutto 才会更加完善，感谢你的贡献**
