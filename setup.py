from setuptools import setup


setup(name="dict_to_protobuf",
      description="convert a dict to a protobuf message",
      py_modules=[
        "dict_to_protobuf"
        ],
      install_requires=[
          'protobuf>=2.5.0, <3.0',
          'fp>=0.2, < 1.0',
        ])
