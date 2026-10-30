# Rakuno APT Apps

个人维护的多应用 Debian 软件包与签名 APT 源，ddns-go 是首个软件包，参考 [homebrew-apps](https://github.com/metalsandbox/homebrew-apps) 的定时更新结构。与 Debian 或 ddns-go 作者无隶属关系。

- 上游：[jeessy2/ddns-go](https://github.com/jeessy2/ddns-go)。仅包装官方稳定版 Linux 二进制，不重新编译。
- 架构：amd64、arm64。目标为使用 systemd 的 Debian 12/13。
- 发布地址：https://metalsandbox.github.io/rakuno-apt-apps/
- 每日 UTC 03:37（北京时间 11:37）检查并构建，也支持 Actions 手动指定上游 tag 和 Debian revision。
- 下载必须通过上游 checksums.txt 校验；GitHub 提供 asset digest 时同时验证。校验值与二进制来自同一上游，不构成独立作者签名验证。
- Release/InRelease 使用本仓库专用 GPG 密钥签名，旧包保存在 gh-pages 分支并进入索引。

## 手动安装

以下步骤由用户手动执行；本仓库构建流程不会在你的服务器上安装或启用服务。
先确认系统已有 curl、gpg、ca-certificates、systemd。安装这些依赖前请自行确认。

```sh
curl -fsSLo /tmp/rakuno-apt-apps.gpg https://metalsandbox.github.io/rakuno-apt-apps/rakuno-apt-apps.gpg
gpg --show-keys --with-fingerprint /tmp/rakuno-apt-apps.gpg
```

核对完整指纹：

```text
6ACB 155E D1C7 D515 F3E0 3279 3E73 0689 2044 7E56
```

确认后添加专用公钥及源：

```sh
sudo install -d -m 0755 /etc/apt/keyrings
sudo install -m 0644 /tmp/rakuno-apt-apps.gpg /etc/apt/keyrings/rakuno-apt-apps.gpg
printf '%s\n' 'deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/rakuno-apt-apps.gpg] https://metalsandbox.github.io/rakuno-apt-apps stable main' | sudo tee /etc/apt/sources.list.d/rakuno-apt-apps.list
sudo apt update
apt-cache policy ddns-go
sudo apt install ddns-go
```

已通过其他方式安装 ddns-go 时，先检查 `systemctl cat ddns-go`、二进制路径与现有配置，备份并完成迁移；本包不会导入或删除旧配置。已有 `/etc/systemd/system/ddns-go.service` 会覆盖本包的服务文件。

## 配置与管理

首次安装后自动启用并启动 systemd 服务。Web 仅监听 `127.0.0.1:9876`，可从自己的电脑建立 SSH 隧道：

```sh
ssh -L 9876:127.0.0.1:9876 wangdongyue@raku-debian
```

浏览器打开 http://localhost:9876 完成配置。运行配置及 API 凭据位于 `/var/lib/ddns-go/config.yaml`，目录权限 0700，由 systemd DynamicUser 管理。服务用动态用户运行，某些依赖 root 权限或访问家目录的自定义命令可能不适用。

```sh
systemctl status ddns-go
sudo systemctl restart ddns-go
journalctl -u ddns-go -n 100 --no-pager
sudo apt update
sudo apt install --only-upgrade ddns-go
apt-cache madison ddns-go
# 回退：把下面的版本替换为 madison 显示的实际旧版
sudo apt install --allow-downgrades ddns-go=<旧版本>
sudo apt remove ddns-go
sudo apt purge ddns-go
```

升级只在服务正在运行时重启，保留已停止/禁用状态。remove 停止并禁用服务；remove 和 purge 都刻意保留 `/var/lib/ddns-go` 中的凭据及配置。卸载不自动删除软件源和公钥。

## 构建与签名

依赖系统现有 Python 3、dpkg-deb、GnuPG、APT、systemd-analyze，无 pip 依赖。若缺少工具，先确认后通过 apt 安装。GitHub runner 使用预装工具。

```sh
python3 scripts/build.py --tag v6.17.7 --revision 1
GNUPGHOME=/path/to/dedicated/key-directory sh scripts/sign.sh
python3 scripts/verify.py
```

`APT_SIGNING_KEY` 仓库 Actions Secret 保存 ASCII-armored 仓库专用私钥。现有密钥 UID 保留最初的 ddns-go 名称，指纹不变，可继续为本源的其他软件包签名。私钥与撤销证书不得提交到任何分支；公钥见 `keys/rakuno-apt-apps.gpg`。修改密钥需同步更新脚本指纹、README 和客户端信任。限制仓库写权限，因为可修改工作流的用户能够使用签名 Secret。

`verify.py` 使用项目内的临时 APT 状态目录验证签名、索引、候选版本及软件包结构，不写系统源、不安装程序。服务实际运行及安装/卸载尚需用户安装后验证。

Actions 在 main 更新、每天定时和手动触发时构建，构建验证成功后自动发布。无新版时仍刷新签名索引。GitHub 定时任务可能延迟，长期无活动的公开仓库可能停用定时任务。Pages 及 gh-pages 产物均公开。失败时保留上一次 Pages 部署。

打包脚本为 MIT，ddns-go 及随包版权文件遵循上游 MIT 许可。

## 扩展应用

这是统一 APT 源，新增应用继续使用相同源地址与签名公钥，无需客户端再添加源。

每个应用需提供独立的上游版本发现、官方来源校验与 Debian 打包步骤。包放入 `repo/pool/main/<首字母>/<包名>/`，各架构 `.deb` 文件以 `_<架构>.deb` 结尾。现有索引生成器会收录 pool 下所有 amd64/arm64 包及旧版本，不限于 ddns-go。新增其他架构时需同步扩展索引和 Release 的 Architectures。

新增包的构建应接入同一个串行发布工作流，在统一生成索引和签名前完成，避免多个工作流相互覆盖 gh-pages。当前 `scripts/build.py` 实现首个 ddns-go 构建与共享索引生成；新增第二个包时应将共享索引生成拆为独立步骤。不要覆盖已有版本文件；修改打包内容必须增加 Debian revision。

## Xperia Flashtool（Debian 13 amd64）

提供 `xperia-flashtool`，包装 Androxyde 官方 0.9.36.0 Linux x86-64 发布包，
保留自带 Java 17 与第三方库。目标为 Debian 13 XFCE 等本地桌面；不提供 ARM 包。
固定 SHA256 校验官方资产，设备库固定为 `4f354572579e62337d56a6b9319f7f8b31b3378a`。
上游源码和设备库源码与 deb 一起公开保存在 pool。此包与 Debian 官方维护版本无隶属关系。

已添加上述统一源和公钥的用户，手动执行：

```sh
sudo apt update
apt-cache policy xperia-flashtool
sudo apt install xperia-flashtool
```

APT 会显示运行库依赖，确认后安装。在 Debian 本机 XFCE 的应用菜单或终端运行
`xperia-flashtool`。不要用 sudo 启动界面。首次启动会复制离线设备库到
`~/.flashTool/devices`，新配置默认 `gitauto=false`，已有配置和设备库不覆盖。
可在程序中自行启用在线设备库同步。

USB 规则只向活动本地桌面会话授权 Sony `0fce` 设备；安装后重新插入手机生效。
SSH 会话本身不获得桌面 USB 权限。软件包不会启动刷机、解锁手机或操作手机数据。
固件 FTF 需另行准备。安装、卸载不删除 `~/.flashTool`。

CI 在临时 Debian 13 容器内验证依赖安装、Java、普通用户图形启动与离线设备库，
不连接手机，不验证真实硬件刷写。发布后再验证 HTTPS 签名源和 APT 候选版本。
