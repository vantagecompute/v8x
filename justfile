#!/usr/bin/env just --justfile

uv := require("uv")

project_dir := justfile_directory()
src_dir := project_dir / "v8x"
tests_dir := project_dir / "tests"

export PY_COLORS := "1"
export PYTHONBREAKPOINT := "pdb.set_trace"
export PYTHONPATH := src_dir

uv_run := "uv run --frozen --extra dev"

[private]
default:
    @just help

# Regenerate uv.lock
[group("dev")]
lock:
    uv lock

# Build graphify knowledge graph in graphify-out/
[group("graphify")]
graphify:
    @command -v graphify >/dev/null 2>&1 || (echo "graphify CLI not found. Install it with: uv tool install --upgrade graphifyy" && exit 1)
    @echo "Building graphify graph in graphify-out/..."
    graphify extract .

# Incrementally update graphify knowledge graph in graphify-out/
[group("graphify")]
graphify-update:
    @command -v graphify >/dev/null 2>&1 || (echo "graphify CLI not found. Install it with: uv tool install --upgrade graphifyy" && exit 1)
    @echo "Updating graphify graph in graphify-out/..."
    graphify update .

# Install Docusaurus dependencies
[group("docusaurus")]
docs-install:
    @echo "📦 Installing Docusaurus dependencies..."
    cd docusaurus && yarn install

# Start Docusaurus development server
[group("docusaurus")]
docs-dev: docs-install
    @echo "🚀 Starting Docusaurus development server..."
    cd docusaurus && yarn start

# Start Docusaurus development server on specific port
[group("docusaurus")]
docs-dev-port port="3000": docs-install
    @echo "🚀 Starting Docusaurus development server on port {{port}}..."
    cd docusaurus && yarn start --port {{port}}

# Build Docusaurus for production
[group("docusaurus")]
docs-build: docs-install
    #{{uv_run}} python3 ./scripts/generate_complete_docs.py
    {{uv_run}} python3 ./scripts/update_docs_version.py
    @echo "🏗️ Building Docusaurus for production..."
    cd docusaurus && yarn build

# Serve built Docusaurus site locally
[group("docusaurus")]
docs-serve: docs-build
    @echo "🌐 Serving built Docusaurus site..."
    cd docusaurus && yarn serve

# Clean Docusaurus build artifacts
[group("docusaurus")]
docs-clean:
    @echo "🧹 Cleaning Docusaurus build artifacts..."
    cd docusaurus && rm -rf build .docusaurus

# Show available documentation commands
[group("docusaurus")]
docs-help:
    @echo "📚 Docusaurus Commands:"
    @echo "  docs-install    - Install dependencies"
    @echo "  docs-dev        - Start development server"
    @echo "  docs-dev-port   - Start dev server on specific port"
    @echo "  docs-build      - Build for production"
    @echo "  docs-serve      - Serve built site"
    @echo "  docs-clean      - Clean build artifacts"

# Run static type checker on code
[group("lint")]
typecheck: lock
    {{uv_run}} pyright {{src_dir}}


# Apply coding style standards to code
[group("lint")]
fmt: lock
    {{uv_run}} ruff format {{src_dir}} {{tests_dir}}
    {{uv_run}} ruff check --fix {{src_dir}} {{tests_dir}}

# Check code against coding style standards
[group("lint")]
lint: lock
    {{uv_run}} codespell {{src_dir}}
    {{uv_run}} ruff check {{src_dir}} {{tests_dir}}

# Run unit tests
[group("test")]
unit *args: lock
    {{uv_run}} coverage run \
        --source {{src_dir}} \
        -m pytest \
        --tb native \
        -v -s {{args}} {{tests_dir / "unit"}}
    {{uv_run}} coverage report --fail-under=0
    {{uv_run}} coverage xml -o {{project_dir / "cover_unit" / "coverage.xml"}}

# Run integration tests
[group("test")]
integration *args: lock
    {{uv_run}} coverage run \
        --source {{src_dir}} \
        -m pytest \
        --tb native \
        -v -s {{args}} {{tests_dir / "integration"}}
    {{uv_run}} coverage report --fail-under=0
    {{uv_run}} coverage xml -o {{project_dir / "cover_integration" / "coverage.xml"}}

# Run full (unit + integration) test suite with combined coverage
[group("test")]
coverage-all *args: lock
    mkdir -p {{project_dir / "cover_combined"}}
    {{uv_run}} coverage erase
    # Unit tests (parallel data file)
    if [ -d "{{tests_dir / "unit"}}" ]; then \
        {{uv_run}} coverage run -p --source {{src_dir}} -m pytest --tb native -v -s {{args}} {{tests_dir / "unit"}}; \
    fi
    # Integration tests (parallel data file, only if directory exists)
    if [ -d "{{tests_dir / "integration"}}" ]; then \
        {{uv_run}} coverage run -p --source {{src_dir}} -m pytest --tb native -v -s {{args}} {{tests_dir / "integration"}}; \
    fi
    # Combine parallel data files & report (no fail threshold for combined coverage)
    {{uv_run}} coverage combine
    {{uv_run}} coverage report --fail-under=0
    {{uv_run}} coverage xml -o {{project_dir / "cover_combined" / "coverage.xml"}}

# Create release branch, bump version/lock, tag, and push — triggers CI publish workflows
[group("release")]
release version:
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION="{{version}}"
    BRANCH="release/${VERSION}"
    TAG="v${VERSION}"

    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "Working tree is not clean. Commit or stash changes before releasing." >&2
        exit 1
    fi

    if git ls-remote --exit-code --heads origin "${BRANCH}" >/dev/null 2>&1; then
        echo "Branch ${BRANCH} already exists on origin." >&2
        exit 1
    fi

    if git rev-parse "${TAG}" >/dev/null 2>&1; then
        echo "Tag ${TAG} already exists." >&2
        exit 1
    fi

    if git ls-remote --exit-code --tags origin "refs/tags/${TAG}" >/dev/null 2>&1; then
        echo "Tag ${TAG} already exists on origin." >&2
        exit 1
    fi

    CURRENT_BRANCH="$(git branch --show-current)"
    if git rev-parse --verify --quiet "refs/heads/${BRANCH}" >/dev/null; then
        if [[ "${CURRENT_BRANCH}" != "${BRANCH}" ]]; then
            echo "Checking out existing local branch ${BRANCH} to resume release."
            git checkout "${BRANCH}"
        else
            echo "Continuing on existing branch ${BRANCH}."
        fi
    else
        git checkout -b "${BRANCH}"
    fi

    VERSION="${VERSION}" perl -0pi -e 'BEGIN { die "VERSION is required\n" unless length $ENV{VERSION}; } s/^version = "[^"]+"/version = "$ENV{VERSION}"/m or die "Could not find project version in pyproject.toml\n";' pyproject.toml
    uv lock

    git add pyproject.toml uv.lock

    if git diff --cached --quiet; then
        echo "No version or lockfile changes detected; aborting release." >&2
        exit 1
    fi

    git commit -m "release: bump version to ${VERSION}"

    git tag -a "${TAG}" -m "Release ${VERSION}"
    git push -u origin "${BRANCH}" "${TAG}"
    echo "Released ${TAG} on branch ${BRANCH} — CI will publish artifacts."
