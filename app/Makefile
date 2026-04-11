.PHONY: dev build preview install clean \
       pack dist dist-mac dist-linux dist-win dist-all \
       release release-mac release-linux release-win \
       uv-mac uv-linux uv-win uv-all

# --- Development ---

dev: install
	npx electron-vite dev

build: install
	npx electron-vite build

preview: install
	npx electron-vite preview

install: node_modules

node_modules: package.json
	npm install
	@touch node_modules

clean:
	rm -rf out release node_modules resources/bin

# --- Package (unpacked, for testing) ---

pack: build
	npx electron-builder --dir

# --- Distribute (current platform) ---

dist: build
	npx electron-builder --publish never

# --- Distribute per platform ---

dist-mac: uv-mac build
	npx electron-builder --mac --arm64 --x64 --publish never

dist-linux: uv-linux build
	docker run --rm \
		-v "$(CURDIR)":/app \
		-v "$(CURDIR)/../scripts":/scripts:ro \
		-v "$(CURDIR)/../src":/src:ro \
		-v "$(CURDIR)/../pyproject.toml":/pyproject.toml:ro \
		-v "$(CURDIR)/../uv.lock":/uv.lock:ro \
		-v "$(CURDIR)/release":/app/release \
		-w /app \
		electronuserland/builder:20 \
		bash -c "npm install --silent 2>/dev/null && npx electron-builder --linux --x64 --publish never"

dist-win: uv-win build
	docker run --rm \
		-v "$(CURDIR)":/app \
		-v "$(CURDIR)/../scripts":/scripts:ro \
		-v "$(CURDIR)/../src":/src:ro \
		-v "$(CURDIR)/../pyproject.toml":/pyproject.toml:ro \
		-v "$(CURDIR)/../uv.lock":/uv.lock:ro \
		-v "$(CURDIR)/release":/app/release \
		-w /app \
		electronuserland/builder:wine \
		bash -c "npm install --silent 2>/dev/null && npx electron-builder --win --x64 --publish never"

dist-all: dist-mac dist-linux dist-win

# --- Release (build + publish to GitHub) ---

TAG ?= v$(shell node -p "require('./package.json').version")

release: dist-all publish

release-mac: dist-mac publish

release-linux: dist-linux publish

release-win: dist-win publish

publish:
	@command -v gh >/dev/null || { echo "ERROR: gh CLI not found. brew install gh && gh auth login"; exit 1; }
	@echo "Publishing $(TAG) to GitHub Releases (draft)..."
	cd "$(CURDIR)/.." && \
	  git rev-parse "$(TAG)" >/dev/null 2>&1 || { git tag "$(TAG)" && git push origin "$(TAG)"; }
	@if gh release view "$(TAG)" >/dev/null 2>&1; then \
		gh release upload "$(TAG)" release/*.dmg release/*.AppImage release/*.deb release/*.exe release/*.zip 2>/dev/null --clobber; \
	else \
		gh release create "$(TAG)" release/*.dmg release/*.AppImage release/*.deb release/*.exe release/*.zip 2>/dev/null \
			--draft --title "$(TAG)" --generate-notes; \
	fi
	@echo ""
	@gh release view "$(TAG)" --json url -q .url

# --- Download uv binaries ---

uv-mac: resources/bin/mac/arm64/uv resources/bin/mac/x64/uv

uv-linux: resources/bin/linux/x64/uv

uv-win: resources/bin/win/x64/uv.exe

uv-all: uv-mac uv-linux uv-win

resources/bin/mac/arm64/uv:
	@mkdir -p $(dir $@)
	curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz | tar xz -C /tmp
	cp /tmp/uv-aarch64-apple-darwin/uv $@
	chmod +x $@

resources/bin/mac/x64/uv:
	@mkdir -p $(dir $@)
	curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-apple-darwin.tar.gz | tar xz -C /tmp
	cp /tmp/uv-x86_64-apple-darwin/uv $@
	chmod +x $@

resources/bin/linux/x64/uv:
	@mkdir -p $(dir $@)
	curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz | tar xz -C /tmp
	cp /tmp/uv-x86_64-unknown-linux-gnu/uv $@
	chmod +x $@

resources/bin/win/x64/uv.exe:
	@mkdir -p $(dir $@)
	curl -fsSL -o /tmp/uv-win.zip https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
	unzip -o /tmp/uv-win.zip -d /tmp/uv-win
	cp /tmp/uv-win/uv.exe $@
