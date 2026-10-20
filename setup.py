from setuptools import find_packages, setup

setup(
    name="pretix-checkout-assistant",
    version="0.0.1.dev0",
    description="Experimental pretix customer checkout assistant",
    packages=find_packages(),
    include_package_data=True,
    package_data={"pretix_checkout_assistant": ["static/pretix_checkout_assistant/*.js", "templates/pretix_checkout_assistant/*.html", "locale/*/LC_MESSAGES/*.mo", "locale/*/LC_MESSAGES/*.po"]},
    install_requires=["pretix>=2026.8.0,<2026.9.0"],
    entry_points={"pretix.plugin": ["pretix_checkout_assistant=pretix_checkout_assistant:PretixPluginMeta"]},
)
