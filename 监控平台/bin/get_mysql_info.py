# -*- coding: utf-8 -*- 
import MySQLdb
import sys
import subprocess
import time
import subprocess
import os
import datetime
import random
from fabric.api import env,run,put,get,local 
##### zhou fei 2014-07-28
import getopt
reload(sys)
sys.setdefaultencoding('gbk')
os.getenv("ORACLE_HOME")
os.getenv("LD_LIBRARY_PATH")
os.getenv("NLS_LANG")
os.environ['NLS_LANG'] = 'SIMPLIFIED CHINESE_CHINA.UTF8'
import cx_Oracle

ywpt_db_conf='/home/mysql/admin/bin/newbin/ywpt_db.conf'
tmp_ywpt_db_conf='/home/mysql/admin/bin/newbin/tmp_ywpt_db.conf'

monitor_db={}
tmp_monitor_db={}
mysql_param={}
is_completed='N'

def main():
    global h_dbid,h_type

    try:
        opts, args = getopt.getopt(sys.argv[1:], "Hh:d:t:", ["help", "dbid=","host_type="])
        if len(sys.argv)==1: 
           usage()
           sys.exit(2)
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(2)
    for name,value in opts:
        if name in ("-H","--help"):
           usage()
           sys.exit()
        if name in ("-h","--help"):
           usage()
           sys.exit()
        if name in ("-d","--dbid"):
           h_dbid=value
           print "h_dbid:"+h_dbid
        if name in ("-t","--host_type"):
           h_type=value
           print "G_HOST_TYPE:"+h_type
    if h_type=='subordinatestat':
       chk_mysql_subordinate(h_dbid)
    if h_type=='mysqlstat':
       connect_mysql(h_dbid)
    if h_type=='longsql':
       chk_long_sql(h_dbid)
    if h_type=='sqlresult':
       chk_result_sql(h_dbid)

def read_conf(conf_file,type):
    file_hand=open(conf_file)
    for line in file_hand:
        line=line.strip()
        (name,value)=line.split(':')
        if type=='ywpt':
            monitor_db[name]=value
        if type=='tmp':
            tmp_monitor_db[name]=value
    file_hand.close()

read_conf(ywpt_db_conf,'ywpt')

mysqldb = MySQLdb.connect(host=monitor_db.get('ip'), user=monitor_db.get('user'),passwd=monitor_db.get('pass'),db=monitor_db.get('db'),port=int(monitor_db.get('port')) ,charset="utf8")
mysqlcur=mysqldb.cursor()

def get_table_column(table_owner,table_name):
    global table_column
    global table_column_mysql
    global var_list
    global table_column_cnt
    read_conf(tmp_ywpt_db_conf,'tmp')
    mysqldbtmp =  MySQLdb.connect(host=tmp_monitor_db.get('ip'), user=tmp_monitor_db.get('user'),passwd=tmp_monitor_db.get('pass'),db=tmp_monitor_db.get('db'),port=int(tmp_monitor_db.get('port')), charset="utf8")
    tmpcur=mysqldbtmp.cursor()
    tmpcur.execute("set names utf8")
    tmpcur.execute("SELECT column_name FROM  COLUMNS WHERE table_name=%s ORDER BY ORDINAL_POSITION",(table_name,))
    data=tmpcur.fetchall()
    table_column=''
    table_column_mysql=''
    table_column_cnt=0
    var_list=''
    for x in data:
       table_column_cnt=table_column_cnt+1
       table_column=table_column+str(x[0])+','
       table_column_mysql=table_column_mysql+'`'+str(x[0])+'`'+','
       var_list=var_list+'%s'+','
    table_column=table_column.rstrip(',')
    table_column_mysql=table_column_mysql.rstrip(',')
    var_list=var_list.rstrip(',')






def get_mysql_quota_collect_day_lastval(hostid,dbid,quota_id):
    global mysql_qcdl_lastval,mysql_qcdl_lastval_date
    t_sql="select MAX(gmt_created),count(*) from  b_mysql_quota_collect_day WHERE host_id= "+"'"+hostid+"'"+" and db_id ="+"'"+dbid+"'"+" and quota_id="+"'"+quota_id+"'"
    mysqlcur.execute(t_sql)
    data=mysqlcur.fetchone()
    dt,cnt=data
    if cnt==0:
       mysql_qcdl_lastval=0
       mysql_qcdl_lastval_date='1990-01-01 00:00:00'
    else:
       t_sql="select quota_value from  b_mysql_quota_collect_day WHERE host_id= "+"'"+hostid+"'"+" and db_id ="+"'"+dbid+"'"+" and quota_id="+"'"+quota_id+"'"+" and gmt_created="+"'"+str(dt)+"'"
       mysqlcur.execute(t_sql)
       data= mysqlcur.fetchone()
       mysql_qcdl_lastval=data[0]
       mysql_qcdl_lastval_date=dt
    


def insert_data(table_name,varlist):
                get_table_column('sys',table_name)
                mysqlcur.execute("replace into "+table_name+" ("+table_column_mysql+" ) values ("+var_list+")",(varlist))
                mysqldb.commit()



def get_mysql_pass(t_dbid):
    global username,password,port,ip_addr,host_id,g_h_username,g_h_passwd
    mysqlcur.execute("set names utf8")
    t_sql="SELECT a.db_username,a.db_passwd,a.port,b.ip_addr,a.host_id,b.user_account,b.user_passwd FROM b_db_config a,b_host_config b WHERE a.host_id=b.host_id  and a.db_id=%s   limit 1 "
    mysqlcur.execute(t_sql,(t_dbid,))
    data = mysqlcur.fetchone()
    username,password,port,ip_addr,host_id,g_h_username,g_h_passwd=data

#取得要抓取的指标
def get_mysql_param():
    global g_statu
    g_statu=''
    mysqlcur.execute("SELECT id,upper(quota_name) FROM `b_quota_model` WHERE sys_category=3")
    data=mysqlcur.fetchall()
    for x in data:
        id,name=x
        mysql_param[name]=id
        g_statu=g_statu+",'"+name+"'"
    g_statu=g_statu.lstrip(',') 

def connect_mysql(g_dbid):
    g_completed='N'
    g_gmt_create=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    g_gmt_modify=g_gmt_create
    table_name='b_mysql_quota_collect_day'
    get_mysql_pass(g_dbid)
    get_mysql_param()
    mysqltarget_db = MySQLdb.connect(host=ip_addr, user=username,passwd=password,db='information_schema',port=int(port) ,charset="utf8")
    mysqltarget_cur=mysqltarget_db.cursor()
    tmp_sql="select variable_name,variable_value from GLOBAL_STATUS where upper(variable_name) in ("+g_statu+")"+" union select variable_name,variable_value from GLOBAL_VARIABLES  where upper(variable_name) in ("+g_statu+")"
    mysqltarget_cur.execute(tmp_sql)
    data=mysqltarget_cur.fetchall()
    for x in data:
         v_name,v_value=x
         get_mysql_quota_collect_day_lastval(host_id,g_dbid,str(mysql_param.get(v_name)))
         t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
         info=[t_id,host_id,g_dbid,mysql_param.get(v_name),v_name,v_value,mysql_qcdl_lastval,g_completed,g_gmt_create,g_gmt_modify,mysql_qcdl_lastval_date]
         insert_data(table_name,info)

    #get mysqld cpu used
    tmp_sql="SELECT variable_value FROM GLOBAL_VARIABLES WHERE variable_name ='LOG_ERROR'"
    mysqltarget_cur.execute(tmp_sql)
    data=mysqltarget_cur.fetchone()
    tmp_logfile=data[0]
    env.user=g_h_username
    env.host_string=ip_addr+':22'
    env.password = g_h_passwd
    tmp_mysqlsid_t=run("ps -ef | grep "+"'"+tmp_logfile+"'"+"|grep mysqld|awk '{print $1,$2}'")
    tmp_mysqlsid_t= tmp_mysqlsid_t.split("\r\n")
    for tmp_mysqlsid in tmp_mysqlsid_t:
        tobj_name,t_ojbid=tmp_mysqlsid.split(" ")
        if tobj_name=="mysql":
            tmp_mysqld_cpu=run("top -n1 -b -c -u mysql|grep "+t_ojbid+"|awk '{print $9}'")
            tmp_mysqld_cpu=tmp_mysqld_cpu.split("\r\n")
            v_name='MYSQLD CPU'
            v_value=tmp_mysqld_cpu[0]
            get_mysql_quota_collect_day_lastval(host_id,g_dbid,str(mysql_param.get(v_name)))
            t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
            info=[t_id,host_id,g_dbid,mysql_param.get(v_name),v_name,v_value,mysql_qcdl_lastval,g_completed,g_gmt_create,g_gmt_modify,mysql_qcdl_lastval_date]
            insert_data(table_name,info)    


               # Subordinate_IO_State:1
                  # Main_Host:2
                  # Main_User:3
                  # Main_Port:4
                # Connect_Retry:5
              # Main_Log_File:6
          # Read_Main_Log_Pos:7
               # Relay_Log_File:8
                # Relay_Log_Pos:9
        # Relay_Main_Log_File:10
             # Subordinate_IO_Running:11
            # Subordinate_SQL_Running:12
              # Replicate_Do_DB:13
          # Replicate_Ignore_DB:14
           # Replicate_Do_Table:15
       # Replicate_Ignore_Table:16
      # Replicate_Wild_Do_Table:17
  # Replicate_Wild_Ignore_Table:18
                   # Last_Errno:19
                   # Last_Error:20
                 # Skip_Counter:21
          # Exec_Main_Log_Pos:22
              # Relay_Log_Space:23
              # Until_Condition:24
               # Until_Log_File:25
                # Until_Log_Pos:26
           # Main_SSL_Allowed:27
           # Main_SSL_CA_File:28
           # Main_SSL_CA_Path:29
              # Main_SSL_Cert:30
            # Main_SSL_Cipher:31
               # Main_SSL_Key:32
        # Seconds_Behind_Main:33
# Main_SSL_Verify_Server_Cert:34
                # Last_IO_Errno:35
                # Last_IO_Error:36
               # Last_SQL_Errno:37
               # Last_SQL_Error:38
  # Replicate_Ignore_Server_Ids:39
             # Main_Server_Id:40
                  # Main_UUID:41
             # Main_Info_File:42
                    # SQL_Delay:43
          # SQL_Remaining_Delay:44
      # Subordinate_SQL_Running_State:45
           # Main_Retry_Count:46
                  # Main_Bind:47
      # Last_IO_Error_Timestamp:48
     # Last_SQL_Error_Timestamp:49
               # Main_SSL_Crl:50
           # Main_SSL_Crlpath:51
           # Retrieved_Gtid_Set:52
            # Executed_Gtid_Set:53
                # Auto_Position:54

def  getStatus(conn,query):
     cursor = conn.cursor()
     cursor.execute(query)
     result = cursor.fetchall()
     try:
        return result[0]
     except Exception as e:
        result="subordinatestop"
        return result
    

def chk_mysql_subordinate(g_dbid):
    get_mysql_pass(g_dbid)
    get_mysql_param() 
    g_completed='N'
    g_gmt_create=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    g_gmt_modify=g_gmt_create
    table_name='b_mysql_quota_collect_day'
    mysqltarget_db = MySQLdb.connect(host=ip_addr, user=username,passwd=password,db='information_schema',port=int(port) ,charset="utf8")
    query="show subordinate status"
    status = getStatus(mysqltarget_db,query)
    if status=='subordinatestop':
       a=0
       #t_msg='My:'+ip_addr+':'+'PORT:'+str(port)+':SLAVE STOP!!!!!:'
       #t_tmd5='mysql subordinate stop!!'
       #t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
       #info=[t_id,g_dbid,t_msg,g_completed,t_tmd5,g_gmt_create,g_gmt_modify,'1','6']
       #insert_data('b_error_msg',info)
    else:   
        Seconds_Behind_Main, Subordinate_IO_Running, Subordinate_SQL_Running=status[32],status[10],status[11]
        if Subordinate_IO_Running == 'Yes' and Subordinate_SQL_Running == 'Yes':
             v_name='Seconds_Behind_Main'
             v_name=v_name.upper()
             v_value=Seconds_Behind_Main
             get_mysql_quota_collect_day_lastval(host_id,g_dbid,str(mysql_param.get(v_name)))
             t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
             info=[t_id,host_id,g_dbid,mysql_param.get(v_name),v_name,v_value,mysql_qcdl_lastval,g_completed,g_gmt_create,g_gmt_modify,mysql_qcdl_lastval_date]
             insert_data(table_name,info)  
             #if Seconds_Behind_Main >= 60:
             #    t_msg='My:'+ip_addr+':'+'PORT:'+str(port)+':Behind:'+str(Seconds_Behind_Main)
             #    t_tmd5='mysql status'
             #    t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))  
             #    info=[t_id,g_dbid,t_msg,g_completed,t_tmd5,g_gmt_create,g_gmt_modify,'1','2']
             #    insert_data('b_error_msg',info)
        else:
             t_msg='My:'+ip_addr+':'+'PORT:'+str(port)+':SLAVE STOP!!!!!:'
             t_tmd5='mysql subordinate stop!!'
             t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
             info=[t_id,g_dbid,t_msg,g_completed,t_tmd5,g_gmt_create,g_gmt_modify,'0','6']
             insert_data('b_error_msg',info)
       

def chk_long_sql(g_dbid):
    g_completed='N'
    g_gmt_create=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    g_gmt_modify=g_gmt_create
    tmp_sql="SELECT dbid_max,user_max,ipaddr_max,db_max,sample,query_time_pct_95 FROM  `myawr_query_review_history` WHERE dbid_max=%s  AND ts_max >=DATE_ADD(NOW(),INTERVAL-15 MINUTE)  AND user_max not in ('root','rnd') AND query_time_pct_95>=3"
    mysqlcur.execute(tmp_sql,(g_dbid,))
    t_table_name='b_error_msg'
    data=mysqlcur.fetchall()
    for x in data:
             t_dbid_max,t_user_max,t_ipaddr_max,t_db_max,t_sample,t_query_time_pct_95=x
             t_tmd5='mysql long sql'
             t_msg='My:time more than 3 sec:'+t_sample+' user:'+t_user_max+' From ip:'+t_ipaddr_max+' Db:'+t_db_max+' query time:'+str(t_query_time_pct_95)
             t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
             info=[t_id,g_dbid,t_msg,g_completed,t_tmd5,g_gmt_create,g_gmt_modify,'1','10']
             insert_data(t_table_name,info)

def chk_result_sql(g_dbid):
    g_completed='N'
    g_gmt_create=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    g_gmt_modify=g_gmt_create
    tmp_sql="SELECT dbid_max,user_max,ipaddr_max,db_max,sample,rows_sent_pct_95 FROM  `myawr_query_review_history` WHERE dbid_max=%s  AND ts_max >=DATE_ADD(NOW(),INTERVAL-15 MINUTE) AND user_max not in ('root','rnd') AND rows_sent_pct_95>=500"
    mysqlcur.execute(tmp_sql,(g_dbid,))
    t_table_name='b_error_msg'
    data=mysqlcur.fetchall()
    for x in data:
             t_dbid_max,t_user_max,t_ipaddr_max,t_db_max,t_sample,t_rows_sent_pct_95=x
             t_tmd5='mysql result rows'
             t_msg='My:result more than 500:'+t_sample+' user:'+t_user_max+' From ip:'+t_ipaddr_max+' Db:'+t_db_max+' result row:'+str(t_rows_sent_pct_95)
             t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
             info=[t_id,g_dbid,t_msg,g_completed,t_tmd5,g_gmt_create,g_gmt_modify,'1','11']
             insert_data(t_table_name,info)
    tmp_sql="SELECT dbid_max,user_max,ipaddr_max,db_max,sample,Rows_examined_pct_95 FROM  `myawr_query_review_history` WHERE dbid_max=%s  AND ts_max >=DATE_ADD(NOW(),INTERVAL-15 MINUTE) AND user_max not in ('root','rnd') AND Rows_examined_pct_95>=1000"
    mysqlcur.execute(tmp_sql,(g_dbid,))
    t_table_name='b_error_msg'
    data=mysqlcur.fetchall()
    for x in data:
             t_dbid_max,t_user_max,t_ipaddr_max,t_db_max,t_sample,t_rows_affected_pct_95=x
             t_tmd5='mysql examined rows'
             t_msg='My:examined more than 1000:'+t_sample+' user:'+t_user_max+' From ip:'+t_ipaddr_max+' Db:'+t_db_max+' examined row:'+str(t_rows_affected_pct_95)
             t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
             info=[t_id,g_dbid,t_msg,g_completed,t_tmd5,g_gmt_create,g_gmt_modify,'1','12']
             insert_data(t_table_name,info)

   
def chk_innodb(g_dbid):
    get_mysql_pass(g_dbid)
    get_mysql_param()
    g_completed='N'
    g_gmt_create=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    g_gmt_modify=g_gmt_create
    table_name='b_mysql_quota_collect_day'
    mysqltarget_db = MySQLdb.connect(host=ip_addr, user=username,passwd=password,db='information_schema',port=int(port) ,charset="utf8")
    query="show engine innodb status"
    status = getStatus(mysqltarget_db,query)
    for i in  status:
        print i 




'''
if __name__=="__main__":
       h_dbid=sys.argv[1]   #要访问的db_id
       h_type=sys.argv[2]
       if h_type=='subordinatestat':
          chk_mysql_subordinate(h_dbid)
       if h_type=='mysqlstat':
          connect_mysql(h_dbid)
       if h_type=='longsql':
          chk_long_sql(h_dbid)
       if h_type=='sqlresult':
          chk_result_sql(h_dbid)
      # chk_innodb(h_dbid)
'''

def usage():
    print '''
---------------usage:------------------
python get_mysql_info_new.py -d dbid -t type (subordinatestat,mysqlstat,longsql,sqlresult)
or
python get_mysql_info_new.py --dbid=dbid --host_type=(subordinatestat,mysqlstat,longsql,sqlresult)
---------------------------------------
'''

if __name__=="__main__":
   main()
