#!/usr/bin/env bash
# Downloads Microsoft's AdventureWorks OLTP sample (MIT licence) into data/adventureworks/.
set -euo pipefail
mkdir -p data/adventureworks && cd data/adventureworks
[ -f instawdb.sql ] || { curl -fL -o aw.zip https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks-oltp-install-script.zip; unzip -q aw.zip; rm aw.zip; }
