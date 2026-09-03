# Releasing to PyPI

PyPI is the index `pip` and `uv` install from. Until a version is on it,
`uv tool install radiowriter` has nothing to find and people install from git
instead.

## What has to exist first

1. **A PyPI account** — [pypi.org/account/register](https://pypi.org/account/register/),
   with two-factor authentication, which is now mandatory for publishing.
2. **The name reserved.** `radiowriter` was free at the time of writing; the
   first upload claims it. Nobody else can take it afterwards.
3. **A tagged version.** `version` in `pyproject.toml` and the git tag should
   agree, or the release page will disagree with what `pip` installed.

## The safe way: Trusted Publishing

You can upload with an API token, but then the token has to live somewhere —
your laptop, or a GitHub secret — and a token that can publish is a token that
can publish something that is not yours.

**Trusted Publishing** removes the token. PyPI is told "the workflow
`release.yml` in `gmadevs/Radiowriter` may publish `radiowriter`", and GitHub
signs each run so PyPI can check it. Nothing is stored anywhere.

Set it up once, before the first release:

1. On PyPI: **Your projects → Publishing → Add a new pending publisher**
2. Fill in:
   - PyPI project name: `radiowriter`
   - Owner: `gmadevs`
   - Repository: `Radiowriter`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. On GitHub: **Settings → Environments → New environment**, named `pypi`

"Pending publisher" is the form to use before the project exists — the first
successful run creates it.

## Trying it on TestPyPI first

[test.pypi.org](https://test.pypi.org) is a full copy of PyPI that nobody
installs from by accident. It is a **separate site with a separate account**:
registering on PyPI does not register you there, and the pending publisher has
to be added again, with `testpypi` as the environment.

**Where a tag goes is decided by its shape**, so trying something out is not a
separate procedure to remember:

| Tag | Goes to |
|---|---|
| `v0.1.0rc1`, `v0.2.0a3`, `v1.0.0b2` | TestPyPI |
| `v0.1.0`, `v1.2.3` | PyPI |

The version in `pyproject.toml` has to say the same thing, and the workflow
stops if it does not — a release page that contradicts what `pip` installed is
a thing nobody notices until it matters. The comparison goes through
`packaging` rather than string equality, because PEP 440 normalises:
`0.1.0-rc1` and `0.1.0rc1` are the same version written two ways.

Push a release candidate, then check the result is installable:

```bash
uv tool install --index-url https://test.pypi.org/simple/ \
                --extra-index-url https://pypi.org/simple/ radiowriter
```

The two index URLs are needed because TestPyPI does not carry Streamlit or
pandas: the package comes from the test index, its dependencies from the real
one.

## Making a release

```bash
# 1. the version, in one place
$EDITOR pyproject.toml          # version = "0.1.1"

# 2. the tests, all of them
python3 check_rules.py && python3 check_structure.py && \
python3 check_search.py && python3 check_journals.py && python3 check_app.py

# 3. tag it and push
git commit -am "Version 0.1.1"
git tag v0.1.1
git push && git push --tags
```

The tag triggers `release.yml`, which builds the wheel and the sdist, uploads
them to PyPI and opens a GitHub release.

A few minutes later:

```bash
uv tool install radiowriter          # or: uv tool upgrade radiowriter
```

## Checking a build before it goes out

```bash
pip install build twine
python -m build                      # writes dist/
twine check dist/*                   # README renders on the project page?
pip install dist/radiowriter-*.whl   # into a throwaway venv
radiowriter --version
```

`twine check` catches the commonest embarrassment: a README that PyPI refuses
to render, leaving the project page blank.

## A version cannot be replaced

Once `0.1.0` is uploaded it is that file forever. A version can be *yanked* —
hidden from new installs while staying available to anything that pinned it —
but never overwritten. Which is why TestPyPI exists, and why release candidates
are worth the extra minute.

## Installing from git in the meantime

Perfectly good, and it needs no index at all:

```bash
uv tool install git+https://github.com/gmadevs/Radiowriter
```

While the repository is private, whoever runs it needs access to it — git will
ask for credentials.
