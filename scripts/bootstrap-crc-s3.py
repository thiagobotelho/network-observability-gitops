#!/usr/bin/env python3
"""Bootstrap S3 only on personal CRC; credentials travel through memory/stdin."""
import argparse,base64,datetime,json,resource,subprocess,sys,time
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true')
parser.add_argument('--context',help='Contexto do CRC; padrão: contexto atual do KUBECONFIG')
args=parser.parse_args()
OC=['oc','--request-timeout=20s']
def call(argv,obj=None):
 p=subprocess.run(OC+argv,input=json.dumps(obj) if obj is not None else None,capture_output=True,text=True,timeout=30)
 if p.returncode:
  if argv[0]=='whoami':
   raise RuntimeError('Autenticação no CRC falhou. Execute oc whoami no mesmo terminal; refaça o login e tente novamente.')
  raise RuntimeError('Falha em oc '+argv[0]+'. Verifique conexão e permissões no contexto selecionado; nenhuma credencial será exibida.')
 return p.stdout
try:
 context=args.context or call(['config','current-context']).strip()
 if not context:raise RuntimeError('Nenhum contexto selecionado. Faça login no CRC antes de continuar.')
 OC.extend(['--context',context])
 server=call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']).strip()
 if server!='https://api.crc.testing:6443':
  raise RuntimeError('Contexto recusado: este bootstrap aceita somente https://api.crc.testing:6443. Selecione o contexto do CRC.')
 call(['whoami']);root=json.loads(call(['get','secret/minio-credentials','-n','openshift-logging','-o','json']))['data']
 expected={'access_key_id':root['root-user'],'access_key_secret':root['root-password']}
 secret=call(['get','secret/netobserv-loki-s3','-n','netobserv','--ignore-not-found','-o','json'])
 if secret.strip():
  actual=json.loads(secret)['data']
  if any(actual.get(k)!=v for k,v in expected.items()):raise RuntimeError('Existing S3 credentials differ; refusing to overwrite')
 elif args.check:raise RuntimeError('Missing netobserv/netobserv-loki-s3')
 else:
  call(['create','-f','-'],{'apiVersion':'v1','kind':'Secret','metadata':{'name':'netobserv-loki-s3','namespace':'netobserv'},'type':'Opaque','data':expected,'stringData':{'endpoint':'http://minio.openshift-logging.svc:9000','bucketnames':'netobserv','region':'us-east-1'}})
 root.clear();expected.clear();p=None
 if args.check:
  deployment=json.loads(call(['get','deployment/minio','-n','openshift-logging','-o','json']))
  if deployment.get('status',{}).get('availableReplicas',0)<1:raise RuntimeError('MinIO is not available')
  print('PASS: CRC target, existing S3 credential consistency and MinIO availability');sys.exit(0)
 name='crc-netobserv-bucket-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
 container={'name':'mc','image':'image-registry.openshift-image-registry.svc:5000/openshift-logging/mc-crc:RELEASE.2025-08-13T08-35-41Z','command':['/bin/sh','-ec'],'args':['for i in $(seq 1 100); do if mc alias set crc http://minio.openshift-logging.svc:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; then mc mb --ignore-existing crc/netobserv >/dev/null && mc stat crc/netobserv >/dev/null && exit 0; fi; sleep 3; done; exit 1'],'env':[{'name':n,'valueFrom':{'secretKeyRef':{'name':'minio-credentials','key':k}}} for n,k in [('MINIO_ROOT_USER','root-user'),('MINIO_ROOT_PASSWORD','root-password')]]+[{'name':'HOME','value':'/tmp'},{'name':'MC_CONFIG_DIR','value':'/tmp/.mc'}],'securityContext':{'runAsNonRoot':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}}}
 call(['create','-f','-'],{'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':'openshift-logging'},'spec':{'backoffLimit':2,'ttlSecondsAfterFinished':1800,'template':{'spec':{'restartPolicy':'OnFailure','containers':[container]}}}})
 for _ in range(70):
  job=json.loads(call(['get','job/'+name,'-n','openshift-logging','-o','json']))
  if job.get('status',{}).get('succeeded',0):print('PASS: netobserv bucket ready; no credentials displayed');sys.exit(0)
  if any(c['type']=='Failed' and c['status']=='True' for c in job.get('status',{}).get('conditions',[])):raise RuntimeError('Bucket bootstrap Job failed; inspect status without printing secrets')
  time.sleep(5)
 raise RuntimeError('Bucket bootstrap timed out')
except Exception as e:
 print('FAIL: '+(str(e) if isinstance(e,RuntimeError) else type(e).__name__),file=sys.stderr);sys.exit(1)
