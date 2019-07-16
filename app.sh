#!/usr/bin/env sh
#
# This script is run by OpenShift's s2i. Here we guarantee that we run desired
# sub-command based on env-variables configuration.
#

case $THOTH_BUILD_ANALYSER_SUBCOMMAND in
	'analyse')
		exec /opt/app-root/bin/python3 thoth-build-analyser analyse
		;;
	'report')
		exec /opt/app-root/bin/python3 thoth-build-analyser report
		;;
	'dependencies')
		exec /opt/app-root/bin/python3 thoth-build-analyser dependencies
		;;
	*)
		echo "Application configuration error - no build-analyser subcommand specified." >&2
		exit 1
		;;
esac
