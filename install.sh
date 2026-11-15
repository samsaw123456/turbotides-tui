#!/bin/sh
# Per-user installation: no sudo, no shell-profile edits, no global Java changes.
set -eu
repo=samsaw123456/turbotides-tui
install_dir=${XDG_DATA_HOME:-$HOME/.local/share}/turbotides-tui/app
bin_dir=$HOME/.local/bin
desktop=yes
local_install=no
uninstall=no
private_java=no
usage() {
    cat <<'EOF'
Usage: sh install.sh [--local] [--private-java] [--prefix DIRECTORY] [--bin-dir DIRECTORY] [--no-desktop]
       sh install.sh --uninstall [--prefix DIRECTORY] [--bin-dir DIRECTORY] [--no-desktop]

Downloads the latest public release and installs Java 25 if needed. --local uses
this extracted release or builds this checkout. Everything installs per-user.
--prefix changes the game directory; --bin-dir changes the command directory.
--no-desktop skips application-menu/Dock integration. Rerun to update or repair.
--private-java downloads the latest private Java 25 even when system Java exists.
EOF
}
die() { printf 'Turbo Tides: %s\n' "$*" >&2; exit 1; }
while [ "$#" -gt 0 ]; do
    case "$1" in
        --local) local_install=yes ;;
        --private-java) private_java=yes ;;
        --prefix|--bin-dir)
            [ "$#" -ge 2 ] || die "$1 needs a directory"
            case "$2" in /*) ;; *) die "$1 must be an absolute path" ;; esac
            if [ "$1" = --prefix ]; then install_dir=$2; else bin_dir=$2; fi
            shift ;;
        --no-desktop) desktop=no ;;
        --uninstall) uninstall=yes ;;
        --help|-h) usage; exit 0 ;;
        *) die "Unknown option: $1 (see --help)" ;;
    esac
    shift
done
case "$install_dir$bin_dir" in *'
'*) die 'Installation paths must not contain newlines.' ;; esac
[ "$install_dir" != / ] && [ "$install_dir" != "$HOME" ] || die 'Choose a dedicated game directory.'
marker=.turbotides-tui-managed
platform=$(uname -s)
case "$platform" in Linux) java_os=linux ;; Darwin) java_os=mac ;; *) die "Unsupported OS: $platform (Linux and macOS supported)" ;; esac
case "$(uname -m)" in x86_64|amd64) java_arch=x64 ;; arm64|aarch64) java_arch=aarch64 ;; *) die 'Only x86-64 and ARM64 are supported.' ;; esac
data_dir=${XDG_DATA_HOME:-$HOME/.local/share}
mac_app="${TURBOTIDES_APPLICATIONS_DIR:-$HOME/Applications}/Turbo Tides TUI.app"
desktop_file=$data_dir/applications/turbotides-tui.desktop
desktop_icon=$data_dir/icons/hicolor/512x512/apps/turbotides-tui.png
command_path=$bin_dir/turbotides-tui
if [ -e "$install_dir" ] || [ -L "$install_dir" ]; then
    [ ! -L "$install_dir" ] && [ -f "$install_dir/$marker" ] || die "Refusing to replace unmanaged directory: $install_dir"
fi
if [ -e "$command_path" ] || [ -L "$command_path" ]; then
    [ -L "$command_path" ] && [ "$(readlink "$command_path")" = "$install_dir/turbotides-tui" ] || die "Refusing to replace unrelated command: $command_path"
fi
if [ "$desktop" = yes ]; then
    if [ "$platform" = Linux ]; then
        if [ -e "$desktop_file" ] || [ -L "$desktop_file" ]; then
            if [ -L "$desktop_file" ] || ! grep -q '^X-TurboTides-Managed=true$' "$desktop_file"; then
                die "Refusing to replace unrelated desktop entry: $desktop_file"
            fi
        elif [ -e "$desktop_icon" ] || [ -L "$desktop_icon" ]; then
            die "Refusing to replace unrelated desktop icon: $desktop_icon"
        fi
        [ ! -L "$desktop_icon" ] || die "Refusing to replace a symlink icon: $desktop_icon"
    else
        [ ! -L "$mac_app" ] || die "Refusing to replace a symlink app: $mac_app"
        [ ! -e "$mac_app" ] || [ -f "$mac_app/Contents/$marker" ] || die "Refusing to replace unmanaged app: $mac_app"
    fi
fi
if [ "$uninstall" = yes ]; then
    [ -f "$install_dir/$marker" ] || die "No managed installation at $install_dir"
    rm -rf -- "$install_dir"
    [ ! -L "$command_path" ] || rm -- "$command_path"
    if [ "$desktop" = yes ]; then
        if [ "$platform" = Linux ]; then
            rm -f -- "$desktop_file" "$desktop_icon"
        elif [ -f "$mac_app/Contents/$marker" ]; then
            rm -rf -- "$mac_app"
        fi
    fi
    printf '%s\n' 'Turbo Tides TUI uninstalled. Your race records have been preserved.'
    exit 0
fi
for required in curl tar sed awk mktemp grep env; do
    command -v "$required" >/dev/null 2>&1 || die "Missing $required. Install it with your system package manager, then rerun this command."
done
if command -v sha256sum >/dev/null 2>&1; then hash_cmd=sha256sum
elif command -v shasum >/dev/null 2>&1; then hash_cmd='shasum -a 256'
else die 'A SHA-256 tool is required (sha256sum or shasum).'; fi
work=$(mktemp -d "${TMPDIR:-/tmp}/turbotides-install.XXXXXXXX")
stage=
backup=
cleanup() {
    [ -z "$stage" ] || rm -rf -- "$stage"
    if [ -n "$backup" ] && [ -d "$backup" ] && [ ! -e "$install_dir" ]; then mv -- "$backup" "$install_dir"; fi
    rm -rf -- "$work"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
download() { curl --fail --location --show-error --silent --retry 3 --connect-timeout 20 --proto '=https' --tlsv1.2 "$1" -o "$2"; }
verify() {
    expected=$1
    case "$expected" in *[!0-9a-fA-F]*|'') die 'Invalid SHA-256 metadata.' ;; esac
    [ "${#expected}" = 64 ] || die 'Invalid SHA-256 length.'
    # hash_cmd contains only one of the fixed commands selected above.
    actual=$($hash_cmd "$2" | awk '{print $1}')
    [ "$actual" = "$expected" ] || die "Checksum mismatch: $2"
}
if [ "$local_install" = yes ]; then
    source_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
    [ -f "$source_dir/scripts/java.sh" ] || die '--local must run from a source checkout or extracted release.'
else
    printf '%s\n' 'Finding the latest Turbo Tides TUI release…'
    download "https://api.github.com/repos/$repo/releases/latest" "$work/release.json"
    tag=$(sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$work/release.json" | head -n 1)
    case "$tag" in v[0-9]*.[0-9]*.[0-9]*) ;; *) die 'Release metadata does not contain a valid version.' ;; esac
    case "$tag" in *[!v0-9.]*) die 'Unexpected release version.' ;; esac
    archive=turbotides-tui-${tag#v}.tar.gz
    release_url=https://github.com/$repo/releases/download/$tag
    download "$release_url/SHA256SUMS" "$work/SHA256SUMS"
    download "$release_url/$archive" "$work/game.tar.gz"
    expected=$(awk -v name="$archive" '$2 == name {print $1}' "$work/SHA256SUMS")
    verify "$expected" "$work/game.tar.gz"
    tar -xzf "$work/game.tar.gz" -C "$work"
    source_dir=$work/turbotides-tui
fi
[ -f "$source_dir/scripts/java.sh" ] && [ -f "$source_dir/turbotides-tui" ] || die 'The release is incomplete.'
app_dir=$install_dir
# shellcheck source=scripts/java.sh
. "$source_dir/scripts/java.sh"
java_kind=jre
if [ ! -f "$source_dir/turbotides-tui.jar" ]; then java_kind=jdk; fi
downloaded_java=no
if [ "$private_java" = yes ] || ! find_java_25 "$java_kind"; then
    [ "$private_java" = yes ] || [ -z "${TURBOTIDES_JAVA_HOME:-}" ] || die 'Correct TURBOTIDES_JAVA_HOME before installing.'
    printf 'Installing a private Eclipse Temurin Java 25 %s…\n' "$java_kind"
    download "https://api.adoptium.net/v3/assets/latest/25/hotspot?architecture=$java_arch&image_type=$java_kind&os=$java_os&vendor=eclipse" "$work/java.json"
    read_temurin_package "$work/java.json" || die 'The Java download metadata could not be read.'
    download "$java_url" "$work/java.tar.gz"
    verify "$java_checksum" "$work/java.tar.gz"
    mkdir "$work/runtime"
    tar -xzf "$work/java.tar.gz" --strip-components=1 -C "$work/runtime"
    TURBOTIDES_JAVA=$work/runtime/bin/java
    if [ ! -x "$TURBOTIDES_JAVA" ]; then TURBOTIDES_JAVA=$work/runtime/Contents/Home/bin/java; fi
    java_is_25 "$TURBOTIDES_JAVA" "$java_kind" || die 'The downloaded Java runtime could not start.'
    downloaded_java=yes
fi
printf 'Using %s\n' "$TURBOTIDES_JAVA"
if [ "$java_kind" = jdk ]; then
    [ -x "$source_dir/gradlew" ] || die 'No game JAR or Gradle wrapper was found.'
    JAVA_HOME=${TURBOTIDES_JAVA%/bin/java} "$source_dir/gradlew" -p "$source_dir" --no-daemon check fatJar
    game_jar=$source_dir/build/libs/turbotides-tui.jar
else game_jar=$source_dir/turbotides-tui.jar; fi
[ -f "$game_jar" ] || die 'The build did not produce turbotides-tui.jar.'
"$TURBOTIDES_JAVA" -jar "$game_jar" --version || die 'The game could not start; the existing installation was kept.'
if [ "$desktop" = yes ]; then
    if [ "$platform" = Linux ]; then required_icon=icon-512.png; else required_icon=icon.icns; fi
    [ -f "$source_dir/assets/$required_icon" ] || die "The release is missing $required_icon."
fi
mkdir -p -- "$(dirname -- "$install_dir")" "$bin_dir"
stage=$(mktemp -d "$(dirname -- "$install_dir")/.turbotides-stage.XXXXXXXX")
mkdir "$stage/scripts" "$stage/assets"
cp -- "$game_jar" "$stage/turbotides-tui.jar"
cp -- "$source_dir/turbotides-tui" "$stage/turbotides-tui"
cp -- "$source_dir/scripts/java.sh" "$stage/scripts/java.sh"
for filename in icon-512.png icon-128.png icon.svg icon.icns; do
    [ ! -f "$source_dir/assets/$filename" ] || cp -- "$source_dir/assets/$filename" "$stage/assets/$filename"
done
for filename in README.md LICENSE THIRD_PARTY.md VERSION; do
    [ ! -f "$source_dir/$filename" ] || cp -- "$source_dir/$filename" "$stage/$filename"
done
if [ -d "$source_dir/docs" ]; then cp -R -- "$source_dir/docs" "$stage/docs"; fi
if [ -d "$source_dir/licenses" ]; then
    cp -R -- "$source_dir/licenses" "$stage/licenses"
elif [ -f "$source_dir/src/main/resources/art/PhippyRescue-MIT.txt" ]; then
    mkdir "$stage/licenses"
    cp -- "$source_dir/src/main/resources/art/PhippyRescue-MIT.txt" "$stage/licenses/PhippyRescue-MIT.txt"
fi
if [ "$downloaded_java" = yes ]; then
    mv -- "$work/runtime" "$stage/runtime"
elif [ -d "$install_dir/runtime" ]; then
    cp -R -- "$install_dir/runtime" "$stage/runtime"
fi
case "$TURBOTIDES_JAVA" in "$work"/*|"$install_dir"/*) ;; *) printf '%s\n' "$TURBOTIDES_JAVA" > "$stage/java.path" ;; esac
printf '%s\n' 'Managed by the Turbo Tides TUI installer.' > "$stage/$marker"
chmod +x "$stage/turbotides-tui"
if [ -d "$install_dir" ]; then
    backup=$(mktemp -d "$(dirname -- "$install_dir")/.turbotides-previous.XXXXXXXX")
    rmdir "$backup"
    mv -- "$install_dir" "$backup"
fi
mv -- "$stage" "$install_dir"
stage=
[ -z "$backup" ] || rm -rf -- "$backup"
backup=
ln -sf -- "$install_dir/turbotides-tui" "$command_path"
if [ "$desktop" = yes ]; then
    if [ "$platform" = Linux ]; then
        mkdir -p "$data_dir/applications" "$data_dir/icons/hicolor/512x512/apps"
        cp "$install_dir/assets/icon-512.png" "$desktop_icon"
        # Desktop Exec quoting has its own escaping rules, including percent fields.
        # env keeps the game path in an argument: Gio validates the executable
        # before expanding %% fields, so a percent in an executable path fails.
        # shellcheck disable=SC2016
        desktop_exec=$(printf '%s' "$install_dir/turbotides-tui" | sed 's/\\/\\\\\\\\/g; s/"/\\\\"/g; s/`/\\\\`/g; s/\$/\\\\$/g; s/%/%%/g')
        cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=Turbo Tides TUI
Comment=Drift and boost through six colourful terminal circuits
Exec=env "$desktop_exec"
Icon=turbotides-tui
Terminal=true
Categories=Game;SportsGame;
Keywords=racing;terminal;arcade;
StartupNotify=false
X-TurboTides-Managed=true
EOF
        if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$data_dir/applications"; fi
        printf 'Application menu: %s\n' "$data_dir/applications/turbotides-tui.desktop"
    else
        mkdir -p "$mac_app/Contents/MacOS" "$mac_app/Contents/Resources"
        cp "$install_dir/assets/icon.icns" "$mac_app/Contents/Resources/turbotides.icns"
        printf '%s\n' "$install_dir/turbotides-tui" > "$mac_app/Contents/Resources/launcher.path"
        printf '%s\n' 'Managed by Turbo Tides TUI.' > "$mac_app/Contents/$marker"
        cat > "$mac_app/Contents/MacOS/TurboTides" <<'EOF'
#!/bin/sh
set -eu
contents=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
IFS= read -r game_launcher < "$contents/Resources/launcher.path"
exec /usr/bin/osascript - "$game_launcher" <<'APPLESCRIPT'
on run argv
    tell application "Terminal"
        activate
        do script "exec " & quoted form of item 1 of argv
    end tell
end run
APPLESCRIPT
EOF
        chmod +x "$mac_app/Contents/MacOS/TurboTides"
        cat > "$mac_app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Turbo Tides TUI</string>
<key>CFBundleIdentifier</key><string>io.github.samsaw123456.turbotides-tui</string>
<key>CFBundleExecutable</key><string>TurboTides</string>
<key>CFBundleIconFile</key><string>turbotides.icns</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><true/>
</dict></plist>
EOF
        printf 'Applications launcher: %s (drag it to your Dock)\n' "$mac_app"
    fi
fi
printf '\nInstalled Turbo Tides TUI. Play with:\n  %s\n' "$command_path"
case ":${PATH:-}:" in *":$bin_dir:"*) ;; *) printf 'For the short command, add %s to your PATH.\n' "$bin_dir" ;; esac
