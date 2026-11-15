#!/bin/sh
# Shared Java selection for the installer and both launch paths.

# Adoptium macOS metadata also contains a .pkg installer; select its archive
# package explicitly, rather than the first checksum/link in the response.
read_temurin_package() {
    package_metadata=$(awk '
        /"package"[[:space:]]*:/ { inside_package = 1; next }
        inside_package && /^[[:space:]]*}/ { exit }
        inside_package { print }
    ' "$1")
    java_url=$(printf '%s\n' "$package_metadata" | sed -n 's/.*"link"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    # shellcheck disable=SC2034 # consumed by the caller's checksum verification
    java_checksum=$(printf '%s\n' "$package_metadata" | sed -n 's/.*"checksum"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    case "$java_url" in
        https://github.com/adoptium/temurin25-binaries/releases/download/*.tar.gz) ;;
        *) printf '%s\n' 'Adoptium metadata did not contain a Java 25 tar archive.' >&2; return 1 ;;
    esac
}

java_is_25() {
    [ -x "$1" ] || return 1
    java_major=$("$1" -version 2>&1 | sed -n 's/.*version "\([0-9]*\).*/\1/p' | head -n 1)
    [ "$java_major" = 25 ] || return 1
    [ "${2:-jre}" != jdk ] || [ -x "${1%/java}/javac" ]
}

find_java_25() {
    java_kind=${1:-jre}
    case ${XDG_DATA_HOME:-} in /*) java_data_dir=$XDG_DATA_HOME ;; *) java_data_dir=$HOME/.local/share ;; esac
    TURBOTIDES_JAVA=
    export TURBOTIDES_JAVA
    if [ -n "${TURBOTIDES_JAVA_HOME:-}" ]; then
        if java_is_25 "$TURBOTIDES_JAVA_HOME/bin/java" "$java_kind"; then
            TURBOTIDES_JAVA=$TURBOTIDES_JAVA_HOME/bin/java
            return 0
        fi
        printf '%s\n' 'TURBOTIDES_JAVA_HOME must point to a working Java 25 installation.' >&2
        return 1
    fi
    for java_candidate in "${app_dir:-/nonexistent}/runtime/bin/java" \
        "${app_dir:-/nonexistent}/runtime/Contents/Home/bin/java" \
        "$java_data_dir/turbotides-tui/app/runtime/bin/java" \
        "$java_data_dir/turbotides-tui/app/runtime/Contents/Home/bin/java" \
        "${JAVA_HOME:-/nonexistent}/bin/java" \
        "$(command -v java 2>/dev/null || true)" \
        /usr/lib/jvm/*25*/bin/java \
        /Library/Java/JavaVirtualMachines/*25*/Contents/Home/bin/java \
        /opt/homebrew/opt/openjdk@25/bin/java /usr/local/opt/openjdk@25/bin/java; do
        if java_is_25 "$java_candidate" "$java_kind"; then
            TURBOTIDES_JAVA=$java_candidate
            return 0
        fi
    done
    if [ -f "${app_dir:-/nonexistent}/java.path" ]; then
        IFS= read -r java_candidate < "$app_dir/java.path" || true
        if java_is_25 "$java_candidate" "$java_kind"; then
            TURBOTIDES_JAVA=$java_candidate
            return 0
        fi
    fi
    return 1
}
