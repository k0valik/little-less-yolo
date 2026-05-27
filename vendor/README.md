# vendor/little-coder

This directory contains a clone of your little-coder fork. It is used by the Docker build to install little-coder into the container image.

## Updating your fork

```bash
cd vendor/little-coder
git pull
cd ../..
mise run pi:build    # rebuild the container image
```

## Why it's here

The Dockerfile does `COPY ./vendor/little-coder/ /little-coder-source/` and then `npm install -g .` from that copy. This ensures the container runs your exact fork, not a version pulled from npm.

The nested `.git` directory is ignored by the parent repo's `.gitignore` to keep the build context small.
