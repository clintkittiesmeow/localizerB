# localizer

TODO: Roll in documentation to README.md

Localizer Demonstration Video: https://youtu.be/UWxWPqCuli8

## Dependencies

### Required System Tools
```
gpsd
gpspipe
iwconfig
ifconfig
tshark
```

Useful commands

Delete all results in cwd and below (local only)
find . -type f -name "*-results.csv" -delete

Delete all results in cwd and below (git)
find . -type f -name "*-results.csv" | xargs git rm -f

Rename all old capture meta extension to new extension
find . -type f -name "*-test.csv" -exec rename 's/-test\.csv$/-capture\.csv/' {} \;
