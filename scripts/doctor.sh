#!/bin/sh
# Passive bootstrap: no installation, environment activation or shell profiles.
usage() {
    printf '%s\n' 'Usage: sh scripts/doctor.sh [--profile core|test] | --help'
}
profile=core
case $# in
    0) ;;
    1) if [ "$1" = --help ]; then
           usage
           printf '%s\n' 'Diagnose prerequisites only; no dependency sync or DB operations.'
           exit 0
       fi
       usage
       exit 64 ;;
    2) if [ "$1" != --profile ]; then usage; exit 64; fi
       case $2 in core|test) profile=$2 ;; *) usage; exit 64 ;; esac ;;
    *) usage; exit 64 ;;
esac

if command -v python3.12 >/dev/null 2>&1; then
    interpreter=python3.12
elif command -v python3 >/dev/null 2>&1; then
    interpreter=python3
else
    printf '%s\n' 'FAIL          PYTHON Python 3.12 missing; install/select it separately.' \
        'NOT CHECKED   OTHER_CHECKS Interpreter unavailable.' \
        'NOT CHECKED   DB_RUNTIME Doctor does not query PostgreSQL.'
    exit 1
fi
case $0 in */*) directory=${0%/*} ;; *) directory=. ;; esac
case $directory in /*) ;; *) directory=./$directory ;; esac
directory=$(CDPATH= cd -P "$directory" 2>/dev/null && pwd -P) || {
    printf '%s\n' 'NOT CHECKED   BOOTSTRAP Script location unavailable; review the checkout.'
    exit 2
}
"$interpreter" -I -S -B "$directory/environment_doctor.py" --profile "$profile" 2>/dev/null
result=$?
case $result in
    0) exit 0 ;;
    1|2|64) printf '%s\n' 'Doctor did not complete successfully; review prerequisites or interpreter access.'
             exit "$result" ;;
    126|127) printf '%s\n' 'FAIL          PYTHON Interpreter could not start; select Python 3.12 separately.'
             exit 1 ;;
    *) printf '%s\n' 'NOT CHECKED   BOOTSTRAP Interpreter execution indeterminate; seek Lead review.'
       exit 2 ;;
esac
