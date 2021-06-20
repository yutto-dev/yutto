run:
  python3 -m yutto

test:
  pytest -m '(api or e2e) and not ci_only'
  just clean

release:
  python3 setup.py upload
  just clean-builds

install:
  python3 setup.py build
  python3 setup.py install
  just clean-builds

upgrade-pip:
  python3 -m pip install --upgrade --pre yutto

clean:
  find . -name "*.m4s" -print0 | xargs -0 rm -f
  find . -name "*.mp4" -print0 | xargs -0 rm -f
  find . -name "*.aac" -print0 | xargs -0 rm -f
  find . -name "*.srt" -print0 | xargs -0 rm -f
  find . -name "*.xml" -print0 | xargs -0 rm -f
  find . -name "*.ass" -print0 | xargs -0 rm -f
  find . -name "*.pb" -print0 | xargs -0 rm -f
  rm -rf .pytest_cache/
  find . -maxdepth 1 -type d -empty -print0 | xargs -0 -r rm -r

clean-builds:
  rm -rf build/
  rm -rf dist/
  rm -rf yutto.egg-info/
