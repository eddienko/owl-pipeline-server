#!/bin/bash
# Replace munge.key with munge.key file used in calling slurm client(s)
#sudo cp /tmp/munge.key /tmp/m.key
#sudo chown munge:munge /tmp/m.key
#sudo mv /tmp/m.key /etc/munge/munge.key
#sudo chmod 400 /etc/munge/munge.key

REQ_CPUS=${CONTAINER_CPU_REQUEST:-2}
REQ_MEM=${CONTAINER_MEMORY_LIMIT:-6676}

HOSTNAME=$(/bin/hostname -s)
IPADDR=$(/bin/hostname -i)

SLURM_NAME=${SLURM_NODE:-$HOSTNAME}
SLURM_IP=${SLURM_IP:-$IPADDR}


cp /etc/slurm/slurm.conf slurm.conf
sed -i s/ControlMachine=.*/ControlMachine=$SLURM_NAME/ slurm.conf
sed -i s/ControlAddr=.*/ControlAddr=$SLURM_IP/ slurm.conf
sed -i s/AccountingStorageHost=.*/AccountingStorageHost=$SLURM_IP/ slurm.conf
sed -i s/NodeName=.*/NodeName=$SLURM_NAME\ NodeAddr=$SLURM_IP\ CPUs=${REQ_CPUS}\ RealMemory=${REQ_MEM}\ State=UNKNOWN/ slurm.conf
cp slurm.conf /etc/slurm/slurm.conf
rm slurm.conf

if [[ "${POD_TYPE}" == "DASK_SCHEDULER" ]]; then
  sudo service munge start
  sudo service mysql start
  sudo service slurmdbd start
  sudo mysql -u root < /slurm/initialize-mariadb.sql
  sudo slurmctld
fi

if [[ "${POD_TYPE}" == "DASK_WORKER" ]]; then
  sudo service munge start
  sudo slurmd
fi
