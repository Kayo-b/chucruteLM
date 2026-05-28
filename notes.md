```
./scripts/run_live_policy.sh    --checkpoint output/base-policy    --profile-name tibia    --print-actions
```

```
python scripts/train_behavior_cloner.py --data data/session-005/ --output output/base-policy/ --profile-name tibia
```