#!/bin/bash
# Deallocate the VM after your demo — stops billing for compute.
# Disk (~$0.30/month) is all that's charged while stopped.

az vm deallocate \
  --resource-group glunova-rg \
  --name glunova-vm

echo "VM stopped. Compute billing paused."
echo "To restart: az vm start --resource-group glunova-rg --name glunova-vm"
