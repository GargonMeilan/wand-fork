# wand

Wand makes it easy to configure dash, houdini and a media server utilizing docker & docker-compose.

Legacy now uses a locally hosted, pinned Ruffle runtime and a WebSocket/TCP
bridge. Vanilla also uses Ruffle through its original page and FlashVars; see
[Vanilla integration](docs/vanilla.md). See [Ruffle and Dokploy deployment](docs/ruffle.md)
for HTTPS domains, configuration, validation, limitations and rollback.

For Dokploy, select **`docker-compose.dokploy.yml`**, enable Git submodules and
configure HTTPS domains on `web:80`. PostgreSQL and Redis use stable Docker
volumes outside the Git checkout. Keep the project name unchanged. Existing
bind-mount data is not migrated automatically; read the deployment guide before
switching an installation whose accounts must be preserved.

The base Compose publishes no host ports. For direct access without Dokploy,
add `-f docker-compose.direct.yml` after `-f docker-compose.yml` to publish the
original ports. Do not enable that optional file behind Dokploy's proxy.

> [!NOTE]
> This can also be ran on Windows using WSL.

## Installation script
**Step 1** run the script
```bash
bash <(curl -s https://raw.githubusercontent.com/solero/wand/master/install.sh)
```
**Step 2** Answer Questions which are:
* Database password (Leave blank for random password)
* Hostname (example: `clubpenguin.com`) (Leave empty for localhost)
* External IP Address (Leave empty for localhost)
**Step 3** Run and enjoy.
Run this command:
```bash
$ cd wand && sudo docker-compose -f docker-compose.yml -f docker-compose.direct.yml up
```
## Manual setup

> [!IMPORTANT]
> This is not recommended for beginners. If you're not sure what you're doing, use the install script.

**Step 1** Choose your Linux Distribution

<details>
  <summary>Debian/Ubuntu</summary>

```bash
$ sudo apt update
$ sudo apt install git curl
$ curl -fsSL https://get.docker.com -o get-docker.sh
$ sh get-docker.sh
$ sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
$ sudo chmod +x /usr/local/bin/docker-compose
```
</details>

<details>
  <summary>Fedora/RHEL</summary>
  
```bash
$ sudo dnf update
$ sudo dnf install git curl
$ curl -fsSL https://get.docker.com -o get-docker.sh
$ sh get-docker.sh
$ sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
$ sudo chmod +x /usr/local/bin/docker-compose
```
</details>

<details>
  <summary>Arch based distros</summary>
  
```bash
$ sudo pacman -Syu
$ sudo pacman -S docker docker-compose git curl
$ systemctl start docker.service
$ systemctl enable docker.service
```
</details>


**Step 2** Clone the repository & submodules
```bash
$ git clone --recurse-submodules https://github.com/solero/wand && cd wand
```

**Step 3** Edit the config file (optional, default values are fine for a local setup)
```bash
$ nano .env
```

**Step 4** Start the services
```bash
$ sudo docker-compose -f docker-compose.yml -f docker-compose.direct.yml up
```

**Step 5** You're done!
