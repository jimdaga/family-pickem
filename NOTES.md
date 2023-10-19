# Random Notes

## Dump data from elastic beanstalk to use for local docker dev

1. SSH to EB
```
eb ssh
```

2. Switch to app user and set ENV vars
```
sudo su - webapp

export $(/opt/elasticbeanstalk/bin/get-config --output YAML environment | sed -r 's/: /=/' | xargs)
```

3. Dump data
```
source /var/app/venv/staging-*/bin/activate

cd /var/app/current/

python manage.py dumpdata pickem_api pickem_homepage allauth > pickem.json
```

4. SCP data back to local (run from local)
```
scp -i ~/.ssh/aws-eb2 ec2-user@xxxx:/var/app/current/pickem.json .
```

5. Copy data to localdev
```
docker cp ~/pickem.json familypickem_django:/tmp
```

6. Restore data
```
docker exec -it familypickem_django bash

python manage.py loaddata /tmp/pickem.json
```

## Perform pgdump on eb

1. Install postgres packages
```
yum install -y https://download.postgresql.org/pub/repos/yum/12/redhat/rhel-6-x86_64/postgresql11-libs-12.14-1PGDG.rhel6.x86_64.rpm
yum install -y https://download.postgresql.org/pub/repos/yum/12/redhat/rhel-6-x86_64/postgresql11-12.14-1PGDG.rhel6.x86_64.rpm
yum install -y https://download.postgresql.org/pub/repos/yum/12/redhat/rhel-6-x86_64/postgresql11-server-12.14-1PGDG.rhel6.x86_64.rpm
```

2. Export database settings
```
export $(/opt/elasticbeanstalk/bin/get-config --output YAML environment | sed -r 's/: /=/' | xargs)
```

3. Dump database
```
# pg_dump -Fc -U $RDS_USERNAME -h $RDS_HOSTNAME $RDS_DB_NAME > db.sql
pg_dumpall -U $RDS_USERNAME -h $RDS_HOSTNAME > db.out
```

4. Copy to local
```
scp -i ~/.ssh/aws-eb2 ec2-user@xxxx:/var/app/current/db.sql .
```

5. Copy to localdev
```
docker cp db.sql familypickem_django:/tmp
```

6. Restore 
```
pg_restore -h postgresql -U postgres -d pickem /tmp/db.sql
```
