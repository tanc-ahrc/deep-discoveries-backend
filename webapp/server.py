import os
from flask import Flask, make_response, render_template, request, redirect, url_for, send_from_directory
from flask.json import jsonify
from werkzeug.utils import secure_filename
import tempfile
import sys
import struct
import base64
import numpy as np
import zmq
import io
from scipy import misc
import hashlib
from flask_cors import CORS, cross_origin


TMP_HEATMAP_DIR='/home/deepdiscover/webapp/static/heatmaptmp'
TMP_HEATMAP_URL='https://decade.ac.uk/deepdiscovery/heatmaptmp'
UPLOAD_FOLDER = '/home/deepdiscover/webapp/queryuploads'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
SEARCH_SERVER_HOSTNAME = "tamatoa.eps.surrey.ac.uk"
SEARCH_SERVER_PORT = 4444

app = Flask(__name__,
            static_url_path='',
            static_folder='static',
            template_folder='templates')



def allowed_file(filename):
	return '.' in filename and \
		filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def readQueryPNG(fname):
	try:
		fd = open(fname, 'rb')
		dta = fd.read()
		fd.close()

		print('PNG is %d bytes' % len(dta))
	except Exception as e:
		dta=''

	return dta

def RepresentsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

def runQuery(data):
	
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	portNumber = SEARCH_SERVER_PORT
	socket.connect("tcp://%s:%d" % (SEARCH_SERVER_HOSTNAME, portNumber))

	print("Communicating with tcp://%s:%s" % (SEARCH_SERVER_HOSTNAME, portNumber))
	socket.send(data)
	queryresp = socket.recv()

	indexsize = int(*struct.unpack_from("!i", queryresp, 0))
	millis = int(*struct.unpack_from("!i", queryresp, 4))
	resnum = int(*struct.unpack_from("!i", queryresp, 8))

	print('Got %d results in %d ms (index contained %d images)' % (resnum, millis, indexsize))

	offset = 12
	results = []
	for idx in range(0, resnum):
		mid = int(*struct.unpack_from("!i", queryresp, offset))
		offset = offset + 4
		dist = round(float(*struct.unpack_from("<f", queryresp, offset)),5)
		offset = offset + 4
		debugtxtlen = int(*struct.unpack_from("!i", queryresp, offset))
		offset = offset + 4
		debugtxt = queryresp[offset:(offset + debugtxtlen)]
		print(debugtxt)
		offset = offset + debugtxtlen
		heatmap_len=int(*struct.unpack_from("!i", queryresp, offset))
		offset = offset + 4
		print('Got %d byte heatmap' % heatmap_len)
		heatmappng=queryresp[offset:(offset + heatmap_len)]
		offset = offset + heatmap_len
		heatmappng=base64.b64decode(heatmappng)
		results.append((mid, dist, debugtxt,heatmappng))

	print(results)


	return results


def prepare_packet(query_files, query_aids, query_urls,se,RETNUM):

	print (query_files)
	print (query_aids)
	print (query_urls)

	se=se.encode("utf-8")

	data = struct.pack('!i', RETNUM) + struct.pack('!i', len(se))
	data = data + se

	pngs=[]

	# get files
	for p in query_files:
		pngdata = readQueryPNG(UPLOAD_FOLDER + '/' + p.filename)
		if (len(pngdata)>0):
			pngs.append(pngdata)

	# get urls
	for u in query_urls:
		_, temp_path = tempfile.mkstemp()
		os.remove(temp_path)
		cmd="curl -L '"+u+"' > "+temp_path
		print('Running: '+cmd)
		os.system(cmd)
		pngdata=readQueryPNG(temp_path)
		os.remove(temp_path)
		if (len(pngdata)>300): # likely to be bad file message
			pngs.append(pngdata)

	# get aids
	for a in query_aids:
		if (RepresentsInt(a)):
			pngdata=struct.pack('!i', int(a))
			pngs.append(pngdata)


	data = data + struct.pack('!i', len(pngs))

	for pngdata in pngs:
		data = data + struct.pack('!i', len(pngdata))
		data = data + pngdata

	return(data)


@app.route('/api/upload', methods=['POST'])
@cross_origin()
def upload_file():
	if request.method == 'POST':
		uploaded_files = request.files.getlist("query_file")
		query_aids = request.form.getlist("query_aid")
		query_urls = request.form.getlist("query_url")

		for file in uploaded_files:
			filename = secure_filename(file.filename)
			if filename =='':
				return redirect(request.url) 
			if file and allowed_file(filename):
				file.save(os.path.join(UPLOAD_FOLDER, filename))

		searchOption = str(request.form['searchengine'])
		RETNUM = int(request.form['resultcount'])

		querydata = prepare_packet(uploaded_files, query_aids, query_urls, searchOption,RETNUM)

		queryResults = runQuery(querydata)

		dn=tempfile.mkdtemp(dir=TMP_HEATMAP_DIR)
		dnstem=dn.split('/')[-1]
		heatmapfiles=[]
		idx=1
		for x in queryResults:
			aid=x[0]
			fc_q=x[3]
			fn_q=dn+'/heatmap_'+str(aid)+'.png'
			fp=open(fn_q,'wb')
			fp.write(fc_q)
			fp.close()
			idx=idx+1

		resultFileNames = [{'aid': x[0], 'distance': x[1], 'collection': x[2].decode("utf-8").split('/')[-2], 'url': x[2].decode("utf-8"), 'heatmapurl': TMP_HEATMAP_URL+'/'+dnstem+'/heatmap_'+str(x[0])+'.png'} for x in queryResults]

		response = jsonify(resultFileNames)
		print(response)
		return response

@app.route('/', methods=['GET', 'POST'])
def index():
	if request.method == 'POST':
		uploaded_files = request.files.getlist("query_file")
		query_aids = request.form.getlist("query_aid")
		query_urls = request.form.getlist("query_url")

		for file in uploaded_files:
			filename = secure_filename(file.filename)
			if file and not filename=='' and allowed_file(filename):
				file.save(os.path.join(UPLOAD_FOLDER, filename))

		searchOption = str(request.form['searchengine'])
		RETNUM = int(request.form['resultcount'])

		querydata = prepare_packet(uploaded_files, query_aids, query_urls, searchOption,RETNUM)

		queryResults = runQuery(querydata)

		dn=tempfile.mkdtemp(dir=TMP_HEATMAP_DIR)
		dnstem=dn.split('/')[-1]
		heatmapfiles=[]
		idx=1
		for x in queryResults:
			aid=x[0]
			fc_q=x[3]
			fn_q=dn+'/heatmap_'+str(aid)+'.png'
			fp=open(fn_q,'wb')
			fp.write(fc_q)
			fp.close()
			idx=idx+1

		resultFileNames = [{'aid': x[0], 'distance': x[1], 'collection': x[2].decode("utf-8").split('/')[-2], 'url': x[2].decode("utf-8"), 'heatmapurl': TMP_HEATMAP_URL+'/'+dnstem+'/heatmap_'+str(x[0])+'.png'} for x in queryResults]

		print(resultFileNames)

		return render_template('index.html', results=True, resultset=resultFileNames)

	return render_template('index.html')


if __name__ == "__main__":
	cors = CORS(app,automatic_options=True)
	app.config['CORS_HEADERS'] = 'Content-Type'
	app.run(host = '0.0.0.0', port=2378)

