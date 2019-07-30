#!/usr/bin/env sh
#
# This script is run by OpenShift's s2i. Here we guarantee that we run desired
# sub-command based on env-variables configuration.
#

case $THOTH_BUILD_ANALYZER_SUBCOMMAND in
	'analyze')
		exec /opt/app-root/bin/python3 thoth-build-analyzer analyze
		;;
	'report')
		exec /opt/app-root/bin/python3 thoth-build-analyzer report
		;;
	'dependencies')
		exec /opt/app-root/bin/python3 thoth-build-analyzer dependencies
		;;
	*)
		echo "Application configuration error - no build-analyzer subcommand specified." >&2
		exit 1
		;;
esac
