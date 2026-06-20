# Linux Packaging

Targets:

- `x64`: `x86_64-unknown-linux-gnu`, Debian `amd64`
- `x86`: `i686-unknown-linux-gnu`, Debian `i386`

Artifacts:

- `.deb` package with uninstall support through `apt remove kymorem`.
- Portable `.tar.gz`.
- Portable `.zip` when `zip` is installed.

Required tools:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
sudo apt install -y build-essential dpkg-dev fakeroot zip
```

Build:

```bash
cd KyMoRem
bash packaging/linux/build-linux.sh
```

For 32-bit builds on a 64-bit Linux builder, install the appropriate multilib
toolchain packages for your distribution.
