#!/bin/bash

query_image=4734.jpg
query_aid=13111
query_url='https://s3.eu-west-2.amazonaws.com/deepdiscovery.thumbnails/TNA1/13111.jpg'

retnum=10
engine=Style
endpoint=https://decade.ac.uk/deepdiscovery/api/upload

curl  -L -X POST -F query_url="${query_url}$" -F searchengine=$engine -F resultcount=$retnum ${endpoint} 
curl  -L -X POST -F query_file=@${query_image} -F searchengine=$engine -F resultcount=$retnum ${endpoint} 
curl  -L -X POST -F query_aid=${query_aid} -F searchengine=$engine -F resultcount=$retnum ${endpoint} 
