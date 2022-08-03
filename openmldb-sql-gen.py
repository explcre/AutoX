from autox.autox import AutoX
from autox.autox_competition.util import log
from autox.autox_competition.process_data.feature_type_recognition import Feature_type_recognition
import re

class OpenMLDB_sql_generator():
    def __init__(self, target, train_name, test_name, path, time_series=False, ts_unit=None, time_col=None,
                     metric='rmse', feature_type = {}, relations = [], id = [], task_type = 'regression',
                     Debug = False, image_info={}, target_map={}):
            self.Debug = Debug
            self.info_ = {}
            self.info_['id'] = id
            self.info_['task_type'] = task_type
            self.info_['target'] = target
            self.info_['feature_type'] = feature_type
            self.info_['relations'] = relations
            self.info_['train_name'] = train_name
            self.info_['test_name'] = test_name
            self.info_['metric'] = metric
            self.info_['time_series'] = time_series
            self.info_['ts_unit'] = ts_unit
            self.info_['time_col'] = time_col
            self.info_['image_info'] = image_info
            self.info_['target_map'] = target_map
            
            if Debug:
                log("Debug mode, sample data")
                self.dfs_[train_name] = self.dfs_[train_name].sample(5000)
            if feature_type == {}:
                for table_name in self.dfs_.keys():
                    df = self.dfs_[table_name]
                    feature_type_recognition = Feature_type_recognition()
                    feature_type = feature_type_recognition.fit(df)
                    self.info_['feature_type'][table_name] = feature_type

    def add_feature_column(self, original_feature_type, processsed_column_name_list):
        print("")
        
        feature_type=original_feature_type
        for i in processsed_column_name_list:
            for csv_list in feature_type:
                feature_type[csv_list][i]="num"
            
        print(feature_type['train2.csv'])
        return  feature_type


    def time_series_feature_sql(self):
        #recipe is as follows
        '''
        select col1, 
        sum(col1) over w1 as col1_w1
        xx over w1 as col2_w1
        col_w2
        from table 
        window 
        w1 as ..rows_range/rows between [] (,]
        w2 as ..
        '''
        shift_dict={}
        shift_dict['year']=[1, 2, 3, 4,5, 10, 20]
        shift_dict['month']=[1, 2, 3, 4, 8, 12, 24,60, 120]
        shift_dict['day']=[1, 2, 3, 7, 14, 21, 30]#, 60, 90, 182, 365]
        shift_dict['minute']=[1, 2, 3, 5, 10, 15, 30, 45, 60, 120, 240,720, 1440]
        
        col_name_dict={}
        col_name_dict['time']=['pickup_datetime', 'dropoff_datetime']
        col_name_dict['num']= ['pickup_latitude', 'dropoff_latitude', 'pickup_longitude', 'dropoff_longitude', 'passenger_count', 'trip_duration']
        col_name_dict['cat']=['vendor_id', 'id', 'store_and_fwd_flag']
        
        function_list=['sum', 'avg', 'min', 'max', 'lag0',   'count']#,'log', 'lag0']
        lag_num_list=shift_dict['day']
        toUseLag=True
        if toUseLag:
            for l, lag_num in enumerate(lag_num_list):
                function_list.append('lag'+str(lag_num))
                function_list.append('lag'+str(lag_num)+'-0')
        
        
        
        table_list=['t1']
        '''
        w AS (PARTITION BY vendor_id ORDER BY pickup_datetime ROWS_RANGE BETWEEN 1d PRECEDING AND CURRENT ROW),
        w2 AS (PARTITION BY passenger_count ORDER BY pickup_datetime ROWS_RANGE BETWEEN 1d PRECEDING AND CURRENT ROW);
        '''
        
        window_list=[]
        
        window_dict_t={"name":"w1", 
        "PARTITION BY":"vendor_id", 
        "ORDER BY":"pickup_datetime",
        "ROWS":"ROWS_RANGE",
        "BETWEEN":"1d", 
        "PRE":"PRECEDING AND CURRENT ROW"
        }
        window_dict_t2={"name":"w2", 
        "PARTITION BY":"passenger_count", 
        "ORDER BY":"pickup_datetime",
        "ROWS":"ROWS_RANGE",
        "BETWEEN":"1d", 
        "PRE":"PRECEDING AND CURRENT ROW"
        }
        '''
        window_dict_t['name']="w"
        window_dict_t['PARTITION BY']="vendor_id"
        window_dict_t['name']="w"
        window_dict_t['name']="w"
        window_dict_t['PRE']="w"
        '''
        window_list.append(window_dict_t)
        window_list.append(window_dict_t2)
        sql="SELECT "
        multi_operator_func_list=['lag']
        #current_window_name="w1"
        processsed_column_name_list=[]
        for w, window in enumerate(window_list):
            
            for col_name_i, col_name in enumerate(col_name_dict['num']):
                sql+=col_name
                sql+=","
                for func_i,  func in  enumerate(function_list):
                    have_multi_op=False
                    multi_op_index=0
                    func_processed_name=func.replace("-", "minus").replace("+", "add").replace("*", "multiply").replace("/", "divide")
                    for op_i, op in enumerate(multi_operator_func_list):
                        if func.startswith(op):
                            sql+=op
                            have_multi_op=True
                            multi_op_index=op_i
                            break
                    '''
                    if have_multi_op:
                        sql+=multi_operator_func_list[multi_op_index]
                    '''
                    if not have_multi_op:
                        sql+=func
                    sql+='('+col_name
                    if have_multi_op:
                        sql+=","
                        func_splited=re.split("[-|\+|\*|\/]",func)
                        #func_splited=func.split("\-|\+|\*|\/")
                        sql+=func_splited[0][len(multi_operator_func_list[multi_op_index]):]
                        
                    
                    sql+=')'
                    sql+=" OVER "
                    sql+=window["name"]
                    sql+=" AS "
                    sql+=(func_processed_name+"_"+col_name+"_"+window["name"])
                    processsed_column_name_list.append(func_processed_name+"_"+col_name+"_"+window["name"])
                    sql+=","
                    sql+="\n "
                '''
                if i< len(col_name_dict['num'])-1:
                    sql+=","   
                '''
                    
        sql+=" FROM "
        for k,  table_name in  enumerate(table_list):
            sql+=table_name
            if k< len(table_list)-1:
                    sql+=","
        sql+="\n "
        
        sql+=" WINDOW "
        for p, window_now in enumerate(window_list):
            sql+=window_now["name"]
            sql+=" AS ("
            sql+="PARTITION BY "+window_now["PARTITION BY"]
            sql+=" ORDER BY "+window_now["ORDER BY"]
            sql+= " "+window_now["ROWS"]
            sql+=" BETWEEN "+window_now["BETWEEN"]
            sql+=" "+window_now["PRE"]
            if p==len(window_list)-1:
                sql+=")\n"
            else:
                sql+="),\n"
        
        file_num=3
        file_name="feature_data_test_auto_sql_generator"+str(file_num)
        
        sql+="INTO OUTFILE '/tmp/%s';"%file_name
        print("*"*50)       
        print(sql)
        print("*"*50)
        return sql,( self.add_feature_column(self.info_['feature_type'], processsed_column_name_list))
        
        
    def decode_time_series_feature_sql_column(self, topk_feature_list):
        sql=""
        
        return sql
        
        

if __name__ == '__main__':
    #demo dataset can be downloaded in the following website
    #https://www.kaggle.com/c/nyc-taxi-trip-duration/overview
    # 选择数据集
    data_name = './nyc-taxi-trip-duration/'#'汽车销量预测'
    path = './nyc-taxi-trip-duration/'#'../../data/{data_name}'
    #id	vendor_id	pickup_datetime	dropoff_datetime	passenger_count	pickup_longitude	pickup_latitude	dropoff_longitude	dropoff_latitude	store_and_fwd_flag	trip_duration
    #id2875421	2	2016/3/14 17:24	2016/3/14 17:32	1	-73.98215485	40.76793671	-73.96463013	40.76560211	N	455


    #c1,c2,c3,c4,c5,c6,date
    #aaa,11,22,1.2,11.3,1.6361E+12,2021/7/20
    feature_type = {
        'test2.csv': {
            'id':'cat',
            'vendor_id':'cat',
            'pickup_datetime':'datetime',
            'dropoff_datetime':'datetime',
            'passenger_count':'num',
            'pickup_longitude':'num',
            'pickup_latitude':'num',
            'dropoff_longitude':'num',
            'dropoff_latitude':'num',
            'store_and_fwd_flag':'cat'#,
            #'trip_duration':'num'
        },
        'train2.csv': {
            'id':'cat',
            'vendor_id':'cat',
            'pickup_datetime':'datetime',
            'dropoff_datetime':'datetime',
            'passenger_count':'num',
            'pickup_longitude':'num',
            'pickup_latitude':'num',
            'dropoff_longitude':'num',
            'dropoff_latitude':'num',
            'store_and_fwd_flag':'cat',
            'trip_duration':'num'
        },
        'train-day.csv': {
            'id':'cat',
            'vendor_id':'cat',
            'pickup_date':'datetime',
            'dropoff_date':'datetime',
            'passenger_count':'num',
            'pickup_longitude':'num',
            'pickup_latitude':'num',
            'dropoff_longitude':'num',
            'dropoff_latitude':'num',
            'store_and_fwd_flag':'cat',
            'trip_duration':'num'
        }
    }
    myOpenMLDB_sql_generator = OpenMLDB_sql_generator(target = 'trip_duration', train_name = 'train2.csv', test_name = 'test2.csv',
                   id = ['id', 'vendor_id'], path = path, time_series=True, ts_unit='min',time_col = ['pickup_datetime','dropoff_datetime'],
                   feature_type = feature_type)
                   
    output_sql, processsed_feature_type=myOpenMLDB_sql_generator.time_series_feature_sql()
    print("*"*25+"processed_feature_type"+"*"*25)
    print(processsed_feature_type)
    print("*"*80)
    
    
    ########################
    #TODO: send query to OpenMLDB and get processed feature data csv file
    
    ########################
    autox = AutoX(target = 'trip_duration', train_name = 'train2.csv', test_name = 'test2.csv',
                   id = ['id', 'vendor_id'], path = path, time_series=True, ts_unit='min',time_col = ['pickup_datetime','dropoff_datetime'],
                   feature_type = feature_type)
                   
                   
    top_features, train_fe, test_fe = autox.get_top_features_ts()
    print(top_features)


    train_fe.head()
    test_fe.head()
    
    
    final_sql=myOpenMLDB_sql_generator.decode_time_series_feature_sql_column(top_features)
    print("*"*25+"final_sql"+"*"*25)
    print(final_sql)
    print("*"*80)
    
    ########################
    #TODO: send query to OpenMLDB and get final top-k feature data csv file
    
    ########################
