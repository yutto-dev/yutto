# 支持的链接

本页面主要介绍了我所支持的链接类型，即 `yutto <url>` 中的 `<url>` 具体可以是哪些值。

## 一表速览

<!-- prettier-ignore -->
| 类型 | 是否支持选集 | 示例链接 | 默认路径模板 |
| - | - | - | - |
| 投稿视频 | - | `https://www.bilibili.com/video/BV1vZ4y1M7mQ/` <br/> `https://www.bilibili.com/video/av371660125/` <br/> `https://www.bilibili.com/video/BV1vZ4y1M7mQ?p=1` <br/> `av371660125` <br/> `BV1vZ4y1M7mQ` | `{title}` |
| 投稿视频 <sup>批量</sup> | :white_check_mark: | `https://www.bilibili.com/video/BV1vZ4y1M7mQ/` <br/> `https://www.bilibili.com/video/av371660125/`  <br/> `av371660125` <br/> `BV1vZ4y1M7mQ` | `{title}/{name}` |
| 番剧 | - | `https://www.bilibili.com/bangumi/play/ep395211` <br/> `ep395211` | `{name}` |
| 番剧 <sup>批量</sup> | :white_check_mark: | `https://www.bilibili.com/bangumi/play/ep395211` <br/> `https://www.bilibili.com/bangumi/play/ss38221` <br/> `https://www.bilibili.com/bangumi/media/md28233903` <br/> `ep395211` <br/> `ss38221` <br/> `md28233903` | `{title}/{name}` |
| 课程 | - | `https://www.bilibili.com/cheese/play/ep6902` | `{name}` |
| 课程 <sup>批量</sup> | :white_check_mark: | `https://www.bilibili.com/cheese/play/ep6902` <br/> `https://www.bilibili.com/cheese/play/ss298` | `{title}/{name}` |
| 用户指定收藏夹 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/favlist?fid=1306978874&ftype=create` | `{username}的收藏夹/{series_title}/{title}/{name}` |
| 当前用户稍后再看 <sup>批量</sup> | :x: | `https://www.bilibili.com/watchlater` <br/> `https://www.bilibili.com/list/watchlater` | `稍后再看/{title}/{name}` |
| 用户全部收藏夹 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/favlist` | `{username}的收藏夹/{series_title}/{title}/{name}` |
| UP 主个人空间 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/video` | `{username}的全部投稿视频/{title}/{name}` |
| 合集 <sup>批量</sup> | :white_check_mark: | `https://space.bilibili.com/3546619314178489/lists?sid=3221717?type=season` <br/> `https://space.bilibili.com/3546619314178489/channel/collectiondetail?sid=3221717`<sup>旧版页面</sup> <br/> `https://space.bilibili.com/100969474/favlist?fid=3221717&ftype=collect&ctype=21` | `{series_title}/{title}` |
| 视频列表 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/lists/1947439?type=series` <br/> `https://space.bilibili.com/100969474/channel/seriesdetail?sid=1947439`<sup>旧版页面</sup> <br/> `https://www.bilibili.com/list/100969474?sid=1947439` | `{series_title}/{title}/{name}` |

本表格展示了我所支持的所有类型的链接，以及最终下载的文件结构。

值得注意的是，这里标记「批量」的视频都必须通过 `-b/--batch` 参数来下载，否则会按照单个视频来解析下载。

::: tip 其他链接

此外只要最终会重定向到我所支持的链接我都可以解析，比如以 `https://b23.tv/` 开头的短链接和 SEO 页面链接。

:::

## 投稿视频

### 投稿视频单 P

对于投稿视频，AV 号、BV 号的链接我都会支持，对于没有 `?p=n` 选集参数的页面，默认会认为是第一话。

```bash
yutto https://www.bilibili.com/video/BV1vZ4y1M7mQ/
yutto https://www.bilibili.com/video/av371660125/
yutto "https://www.bilibili.com/video/BV1vZ4y1M7mQ/?p=1"
```

另外，我还支持直接直接使用 AV 号和 BV 号作为视频链接的唯一标识符。

```bash
yutto BV1vZ4y1M7mQ
yutto av371660125
yutto "BV1vZ4y1M7mQ?p=1"
```

### 投稿视频全集 <Badge type="tip" text="批量" /><Badge type="tip" text="支持选集" />

与投稿视频单集相同，这同样支持 AV 号和 BV 号的链接，但 `?p=n` 的选集参数在此时是无效的，我会认为这只是一个入口链接，而你既然指定了要批量下载，那么我会解析该投稿视频的全集。如果你仍然想要指定下载剧集，请参考选集参数 `-p/--episodes`。

```bash
yutto -b https://www.bilibili.com/video/BV1vZ4y1M7mQ/
yutto -b https://www.bilibili.com/video/av371660125/
yutto -b BV1vZ4y1M7mQ
yutto -b av371660125
yutto -b "BV1vZ4y1M7mQ?p=2" # 仍然会下载全集
yutto -b BV1vZ4y1M7mQ -p 2 # 这样才会只下载第二话
```

## 番剧

### 番剧单话

番剧的话，主要有三种入口链接，分别是能够代表单话唯一标识符的 EP 号链接、代表整季番剧的 MD 号和 SS 号。

对于单话下载来说，MD 号和 SS 号均无法定位到具体某一话，因此单话下载不支持 MD 号和 SS 号，仅支持 EP 号。

```bash
yutto https://www.bilibili.com/bangumi/play/ep395211
yutto ep395211
```

### 番剧全集 <Badge type="tip" text="批量" /><Badge type="tip" text="支持选集" />

对于番剧全集来说，MD 号、SS 号、EP 号均可以定位到这个番剧，因此是都支持的。

```bash
yutto -b https://www.bilibili.com/bangumi/play/ep395211
yutto -b https://www.bilibili.com/bangumi/play/ss38221
yutto -b https://www.bilibili.com/bangumi/media/md28233903
yutto -b ep395211
yutto -b ss38221
yutto -b md28233903
```

当然，如果需要选集请使用 `-p/--episodes` 参数。

```bash
yutto -b md28233903 -p 2
```

## 课程

### 课程单集

课程的链接是以 `cheese` 开头的，与番剧非常类似，课程也是支持 EP 号的。

```bash
yutto https://www.bilibili.com/cheese/play/ep6902
```

注意，课程并不支持直接使用 EP 号作为唯一标识符，因为这会和番剧混淆。

### 课程全集 <Badge type="tip" text="批量" /><Badge type="tip" text="支持选集" />

课程全集的下载方式也和番剧很类似，你可以使用 EP 号或者 SS 号来下载。

```bash
yutto -b https://www.bilibili.com/cheese/play/ep6902
yutto -b https://www.bilibili.com/cheese/play/ss298
```

同样，你不可以直接使用 EP 号和 SS 号作为唯一标识符来下载以免混淆。

## 用户个人空间

::: warning ⚠️ 注意

请注意公开性，比如在未登录的情况下，未公开的收藏夹是无法下载的，这可以在 `个人中心` -> `设置` 中进行调节。

:::

### 用户全部投稿视频 <Badge type="tip" text="批量" />

如果需要下载全部投稿，只需要 `个人中心` -> `投稿` 页面链接即可。

```bash
yutto -b https://space.bilibili.com/100969474/video
```

### 用户全部收藏夹 <Badge type="tip" text="批量" />

如果需要下载全部收藏夹，只需要 `个人中心` -> `收藏` 页面链接即可。

```bash
yutto -b https://space.bilibili.com/100969474/favlist
```

::: warning ⚠️ 注意

用户收藏夹往往非常庞大，解析时很容易触发反爬机制。如遇该问题请稍等片刻后重试。（emmm，如果视频太多的话还是建议逐个收藏夹下载……）

:::

### 指定收藏夹 <Badge type="tip" text="批量" />

对于指定收藏夹，自然就是在收藏页面再次点击具体收藏夹名称后的页面。

```bash
yutto -b "https://space.bilibili.com/100969474/favlist?fid=1306978874"
```

### 当前用户稍后再看 <Badge type="tip" text="批量" />

稍后再看的页面链接也是支持的。

```bash
yutto -b https://www.bilibili.com/watchlater
```

当然，由于你无权访问其他用户的稍后再看，这里只支持当前用户的稍后再看下载。另一方面，这强依赖于你的登录状态，如果你处于未登录状态，那么我当然也是无法获取到你的稍后再看列表的哦～

### 合集和列表 <Badge type="tip" text="批量" />

与其他的相同，你可以在 `个人中心` -> `合集`（旧版页面为 `合集和列表`） 进入具体列表获取对应合集/列表的链接。

```bash
# 合集
yutto -b "https://space.bilibili.com/3546619314178489/lists?sid=3221717?type=season"
yutto -b "https://space.bilibili.com/3546619314178489/channel/collectiondetail?sid=3221717" # 旧版页面链接
# 列表
yutto -b "https://space.bilibili.com/100969474/lists/1947439?type=series"
yutto -b "https://space.bilibili.com/100969474/channel/seriesdetail?sid=1947439" # 旧版页面链接
```

另外，视频列表的播放页面也可以唯一定位该视频列表

```bash
yutto -b "https://www.bilibili.com/list/100969474?sid=1947439"
```

## 任务列表

如果你需要一次开启多个任务，可以试试将任务列表写在一个文件中，每行列出一个任务的参数。

```text
https://www.bilibili.com/bangumi/play/ss38221/ --batch -p $
https://www.bilibili.com/bangumi/play/ss38260/ --batch -p $
```

然后运行

```bash
yutto file:///path/to/list
```

即可分别下载这两个番剧的最新一话。

我会将这样的 file scheme 链接视为一个任务列表进行解析，为了方便使用，直接使用相对或者绝对路径也是可以的

```bash
yutto ./path/to/list
```

值得注意的是，在文件列表各项里的参数优先级是高于命令里的优先级的，比如文件中使用：

```text
rimuru1 --batch -p $ --no-danmaku --vcodec="hevc:copy"
rimuru2 --batch -p $
```

而命令中则使用

```text
yutto file:///path/to/list --vcodec="avc:copy"
```

最终下载的 `rimuru1` 会是 `"hevc:copy"`，而 `rimuru2` 则会是 `"avc:copy"`

另外说一点，列表也是支持嵌套的哦（虽然没什么用 2333）

## 配置别名

除去使用以上所示的链接，你可以通过配置别名来避免每次下载都去视频页面找链接。

比如你可以为《転スラ日記》起一个别名 `rimuru-nikki`，我们将其存在一个文件中 `~/yutto-aliases`

```text
rimuru-nikki=https://www.bilibili.com/bangumi/play/ss38221/
```

之后下载最新话只需要

```bash
yutto -b rimuru-nikki --alias-file=~/yutto-aliases
```

当然，文件列表也是支持 alias 的，你完全可以为你的常用列表起一个别名，一个比较特别的用例是将你所有追番的内容放在一个文件里，然后为该文件起一个别名（比如 `subscription`），这样只需要 `yutto subscription --alias-file path/to/alias/file` 就可以达到追番效果啦～
