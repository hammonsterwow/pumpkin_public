from setuptools import find_packages, setup

package_name = 'robot_controller'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        (
            'share/' + package_name,
            ['package.xml'],
        ),
    ],
    install_requires=[
        'setuptools',
    ],
    zip_safe=True,
    maintainer='Pumpkin Team',
    description='Robot controller package for the Pumpkin Physical AI project',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'stt_node = robot_controller.stt_node:main',
            'nlu_node = robot_controller.nlu_node:main',
            'decision_node = robot_controller.decision_node:main',
            'response_manager_node = robot_controller.response_manager_node:main',
            'action_node = robot_controller.action_node:main',
            'order_submission_node = robot_controller.order_submission_node:main',
            'head_motion_node = robot_controller.head_motion_node:main',
            'face_display_node = robot_controller.face_display_node:main',
            'tts_node = robot_controller.tts_node:main',
            'vision_node = robot_controller.vision_node:main',
            'face_personalization_node = robot_controller.face_personalization_node:main',
            'motor_controller_node = robot_controller.motor_controller_node:main',
        ],
    },
)
