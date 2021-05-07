run:
  python3 -m yutto

test:
  python3 -m pytest

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
  find . -name "*.xml" -print0 | xargs -0 rm -f
  find . -name "*.srt" -print0 | xargs -0 rm -f
  find . -name "*.ass" -print0 | xargs -0 rm -f

clean-builds:
  rm -rf build/
  rm -rf dist/
  rm -rf yutto.egg-info/
