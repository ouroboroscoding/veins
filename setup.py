from setuptools import setup

with open('README.md', 'r') as oF:
	long_description=oF.read()

setup(
	name='veins',
	version='1.0.0',
	description='Veins contains a service to run websocket communication',
	long_description=long_description,
	long_description_content_type='text/markdown',
	url='https://ouroboroscoding.com/body/veins',
	project_urls={
		'Documentation': 'https://ouroboroscoding.com/body/veins',
		'Source': 'https://github.com/ouroboroscoding/veins',
		'Tracker': 'https://github.com/ouroboroscoding/veins/issues'
	},
	keywords=['rest', 'microservices'],
	author='Chris Nasr - Ouroboros Coding Inc.',
	author_email='chris@ouroboroscoding.com',
	license='Custom',
	packages=['veins'],
	python_requires='>=3.10',
	install_requires=[
		'config-oc>=1.0.3,<1.1',
		'gevent>=24.2.1,<24.3.1',
		'gevent-websocket>=0.10.1,<0.11',
		'jsonb>=1.0.0,<1.1',
		'namedredis>=1.0.1,<1.1'
	],
	entry_points={
		'console_scripts': ['veins=veins.__main__:cli']
	},
	zip_safe=True
)