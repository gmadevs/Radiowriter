# Releasing to PyPI

PyPI is the index that `pip` and `uv` install from. `radiowriter` has been on
PyPI since version 0.1.0 (3 September 2026). This page describes how to
publish a new version.

A version is published by pushing a git tag that starts with `v`. Nothing
else publishes: a push to `main` does not, and the workflow cannot be started
by hand.

## Requirements

1. A PyPI account, from
   [pypi.org/account/register](https://pypi.org/account/register/), with
   two-factor authentication. PyPI requires it for publishing.
2. A TestPyPI account, if you publish release candidates. TestPyPI is a
   separate site with separate accounts.
3. Trusted Publishing set up on both sites, as described below.
4. The `version` in `pyproject.toml` equal to the tag. The workflow stops if
   they differ.

## Trusted Publishing {#the-safe-way-trusted-publishing}

With an API token, the token has to be stored on your computer or as a GitHub
secret, and anyone who obtains it can publish under the project's name.

Trusted Publishing does not use a stored token. On PyPI you declare that the
workflow `release.yml` in `gmadevs/Radiowriter` may publish `radiowriter`.
GitHub signs each run of the workflow, and PyPI verifies the signature.

Set it up once on each site. The only difference between the two forms is the
environment name:

| | PyPI | TestPyPI |
|---|---|---|
| Where | [pypi.org](https://pypi.org/manage/account/publishing/) | [test.pypi.org](https://test.pypi.org/manage/account/publishing/) |
| Project name | `radiowriter` | `radiowriter` |
| Owner | `gmadevs` | `gmadevs` |
| Repository | `Radiowriter` | `Radiowriter` |
| Workflow | `release.yml` | `release.yml` |
| Environment | `pypi` | `testpypi` |

The two environments also have to exist on GitHub. Create them under
**Settings → Environments → New environment**, named `pypi` and `testpypi`.

For a project that does not exist on the site yet, use the "pending
publisher" form. The first successful run creates the project.

::: tip If the workflow fails with `invalid-publisher`
The message is *"valid token, but no corresponding publisher"*, followed by
the claims the workflow sent: `repository`, `workflow_ref` and `environment`.
The form on the site has to match them. The usual causes are a different
environment name, or a publisher added on PyPI when the tag went to TestPyPI
(or the reverse).
:::

## Where a tag is published {#trying-it-on-testpypi-first}

The form of the tag decides the destination:

| Tag | Published to |
|---|---|
| a pre-release, such as `v0.1.0rc1`, `v0.2.0a3`, `v1.0.0b2` | TestPyPI |
| a final version, such as `v0.1.0`, `v1.2.3` | PyPI |

[test.pypi.org](https://test.pypi.org) is a separate copy of PyPI for
testing. Publish a release candidate there before a final version.

The workflow compares the tag with the version in `pyproject.toml` and stops
if they differ. Otherwise the GitHub release page and the installed package
would show different versions. The comparison uses `packaging`, because PEP
440 normalises versions: `0.1.0-rc1` and `0.1.0rc1` are the same version.

After pushing a release candidate, check that it installs:

```bash
uv tool install --index-url https://test.pypi.org/simple/ \
                --extra-index-url https://pypi.org/simple/ radiowriter
```

Both index URLs are needed. TestPyPI does not have Streamlit or pandas, so
the package is installed from TestPyPI and its dependencies from PyPI.

## Making a release

1. Set the version in `pyproject.toml`, for example `version = "0.1.4"`.

2. Run the tests:

   ```bash
   python3 check_rules.py && python3 check_structure.py && \
   python3 check_search.py && python3 check_journals.py && \
   python3 check_library.py && python3 check_bench.py && \
   python3 check_app.py
   ```

3. Commit, tag and push:

   ```bash
   git commit -am "Version 0.1.4"
   git tag v0.1.4
   git push && git push --tags
   ```

The tag starts `release.yml`. The workflow:

1. checks that the tag and the version agree;
2. runs the tests (all the scripts above except `check_library.py`);
3. builds the wheel and the sdist and runs `twine check`;
4. uploads them to PyPI, or to TestPyPI for a pre-release;
5. creates a GitHub release with the files, marked as a pre-release when the
   tag is one.

A few minutes later the version can be installed:

```bash
uv tool install radiowriter          # or: uv tool upgrade radiowriter
```

## Checking a build locally {#checking-a-build-before-it-goes-out}

```bash
pip install build twine
python -m build                      # writes dist/
twine check dist/*                   # checks that PyPI can render the README
pip install dist/radiowriter-*.whl   # in a temporary venv
radiowriter --version
```

If PyPI cannot render the README, the project page is empty. `twine check`
reports this before the upload.

## A published version cannot be replaced {#a-version-cannot-be-replaced}

A file uploaded as version `0.1.0` cannot be changed or uploaded again. A
version can be yanked: it is then hidden from new installs and stays
available to projects that pinned it. It cannot be overwritten. For this
reason, publish a release candidate to TestPyPI before each final version.

## Installing from git {#installing-from-git-instead}

The package can also be installed from the repository, without an index:

```bash
uv tool install git+https://github.com/gmadevs/Radiowriter
```

PyPI gives the last released version. The repository gives the current state
of `main`, which can include unreleased and unfinished changes.
