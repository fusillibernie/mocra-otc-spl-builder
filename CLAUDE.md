# Working in this repo

- Run `scripts/test-quiet.sh`; only run the full verbose suite (`pytest`) when a failure needs investigation.
- Before editing, use the `repo-mapper` agent to find where the code handles a topic. Before committing or pushing, run the `independent-reviewer` agent on the diff. Hooks in `.claude/` enforce both.
- Data packs under `src/*/data/` are validated on every edit. Many records are marked `verified: false`: treat results from them as indicative, not as compliance.
