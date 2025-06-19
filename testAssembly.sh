#! /bin/bash
clear
scripts/run --lang loop assembly --max-registers 8 test.py test.as
spim -file test.as