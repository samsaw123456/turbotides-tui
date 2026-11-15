.PHONY: play check format install package
play:
	./turbotides-tui
check:
	./gradlew check fatJar
format:
	./gradlew ktlintFormat
install:
	./install.sh --local
package: check
	python3 tools/package_release.py --skip-build
