from distutils.core import setup
setup(
  name = 'pygbx',
  packages = ['pygbx'],
  version = '0.1',
  license='GPL3',
  description = 'A Python library to parse GBX files',
  author = 'Adam Bieńkowski',              
  author_email = 'donadigos159@gmail.com',
  url = 'https://github.com/donadigo/pygbx',
  download_url = 'https://github.com/user/reponame/archive/v_01.tar.gz',
  keywords = ['GBX', 'parser', 'TrackMania'],
  install_requires=[           
          'python-lzo',
  ],
  classifiers=[
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: GPL3 License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
  ],
)