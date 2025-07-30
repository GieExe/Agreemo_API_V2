# C:\Users\Giebert\PycharmProjects\agreemo_api\callbacks.py

from flask_socketio import emit  # Import emit directly
from models.reason_for_rejection_model import ReasonForRejection
from models.harvest_model import Harvest
from models.maintenance_model import Maintenance
from models.hardware_component_model import HardwareComponents
from models.hardware_current_status_model import HardwareCurrentStatus
from models.activity_logs.admin_activity_logs_model import AdminActivityLogs
from models.activity_logs.user_activity_logs_model import UserActivityLogs
from models.activity_logs.greenhouse_activity_logs_model import GreenHouseActivityLogs
from models.activity_logs.rejection_activity_logs_model import RejectionActivityLogs
from models.activity_logs.hardware_status_logs_model import HardwareStatusActivityLogs
from models.activity_logs.maintenance_activity_logs_model import MaintenanceActivityLogs
from models.activity_logs.harvest_activity_logs_model import HarvestActivityLogs
from models.activity_logs.hardware_components_activity_logs_model import HardwareComponentActivityLogs
from models.activity_logs.nutrient_controller_activity_logs_model import NutrientControllerActivityLogs


def harvest_update_callback(data, db, socketio):  # Add db and socketio as parameters
    """Callback function to handle harvest updates."""
    print(f"Received harvest update: {data}")
    with db.app.app_context():  # Use db.app.app_context()
        try:
            harvest = Harvest.query.get(data['harvest_id'])
            if harvest:
                harvest_data = {
                    "harvest_id": harvest.harvest_id,
                    "greenhouse_id": harvest.greenhouse_id,
                    "plant_type": harvest.plant_type,
                    "accepted": harvest.accepted,
                    "total_rejected": harvest.total_rejected,
                    "total_yield": harvest.total_yield,
                    "harvest_date": harvest.harvest_date.strftime("%Y-%m-%d"),
                    "notes": harvest.notes,
                    "full_name": f"{harvest.users.first_name} {harvest.users.last_name}",
                }
                socketio.emit('harvest_update', harvest_data)
            else:
                print(f"Harvest with ID {data['harvest_id']} not found")
        except Exception as e:
            print(f"Error fetching harvest: {e}")

def rejection_update_callback(data, db, socketio): # Add db and socketio
    print(f"Received rejection update: {data}")

    with db.app.app_context():
        try:
            rejection = ReasonForRejection.query.get(data['rejection_id'])
            if rejection:
                rejection_data = {
                        "rejection_id": rejection.rejection_id,
                        "greenhouse_id": rejection.greenhouse_id,
                        "too_small": rejection.too_small,
                        "physically_damaged": rejection.physically_damaged,
                        "diseased": rejection.diseased,
                        "rejection_date": rejection.rejection_date.strftime("%Y-%m-%d"),
                        "comments": rejection.comments
                }

                socketio.emit('rejection_update', rejection_data)
            else:
                print(f"Rejection record {data['rejection_id']} not found.")
        except Exception as e:
            print(f"An error occurred: {e}")


def maintenance_update_callback(data, db, socketio): # Add db and socketio
    """Callback function for maintenance updates."""
    print(f"Received maintenance update: {data}")

    with db.app.app_context():
        try:
            maintenance_data = Maintenance.query.get(data['maintenance_id'])
            if maintenance_data:
                maintenance_update = {
                "maintenance_id": maintenance_data.maintenance_id,
                "email": maintenance_data.users.email,
                "title": maintenance_data.title,
                "name":  maintenance_data.name,
                "date_completed": maintenance_data.date_completed.strftime("%Y-%m-%d %H:%M:%S") if maintenance_data.date_completed else None,
                "description": maintenance_data.description,
                }
                socketio.emit('maintenance_update', maintenance_update)

            else:
                print(f"Maintenance Record{data['maintenance_id']} not Found")
        except Exception as e:
            print(f"Error Occured: {e}")



def hardware_component_update_callback(data, db, socketio): # Add db and socketio
     print(f"Received Hardware Component Update : {data}")
     with db.app.app_context():
          try:
               hardware_components_data = HardwareComponents.query.get(data['component_id'])
               if hardware_components_data:
                 hardware_component_update = {
                   "component_id": hardware_components_data.component_id,
                   "greenhouse_id": hardware_components_data.greenhouse_id,
                   "componentName": hardware_components_data.componentName,
                   "date_of_installation": hardware_components_data.date_of_installation.strftime(
                       "%Y-%m-%d %H:%M:%S"
                   ),
                   "manufacturer": hardware_components_data.manufacturer,
                   "model_number": hardware_components_data.model_number,
                   "serial_number": hardware_components_data.serial_number
                 }

                 socketio.emit('hardware_component_update', hardware_component_update) #
               else:
                 print(f"Hardware Component with id : {data['component_id']}, not found. ")
          except Exception as e:
            print(f"Something Error, reading update : {e}")


def hardware_status_update_callback(data, db, socketio): # Add db and socketio parameters
    """Callback function for hardware status activity log updates."""
    print(f"Received Hardware Status Update : {data}")
    with db.app.app_context():
        try:
            hardware_status_data = HardwareCurrentStatus.query.filter_by(
                component_id = data['component_id']
            ).first()
            if hardware_status_data:
                hardware_status_update = {
                    "component_id": hardware_status_data.component_id,
                    "isActive": hardware_status_data.isActive,
                    "greenhouse_id": hardware_status_data.greenhouse_id,
                    "lastChecked": hardware_status_data.lastChecked.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "statusNote": hardware_status_data.statusNote

                }
                socketio.emit("hardware_status_update", hardware_status_update) # updates,.


            else:
                print(f"Invalid component_id:{data['component_id']} or deleted other Users")
        except Exception as e:
            print(f"Failed Query data. : {e}")


def admin_logs_update_callback(data, db, socketio): # Add db and socketio parameters
    """Callback function for admin activity log updates."""
    print(f"Received admin log update: {data}")
    with db.app.app_context():
        try:

            admin_log = AdminActivityLogs.query.get(data['log_id'])
            if admin_log:
                admin_log_data = {
                    "log_id": admin_log.log_id,
                    "login_id": admin_log.login_id,
                    "logs_description": admin_log.logs_description,
                    "log_date": admin_log.log_date.strftime("%Y-%m-%d %H:%M:%S"),

                }

                socketio.emit('admin_logs_update', admin_log_data)
            else:
                print(f"Admin activity log record {data['log_id']} not found.")
        except Exception as e:
            print(f"Error fetching/updating admin activity log: {e}")


def greenhouse_logs_update_callback(data, db, socketio):  # Add db and socketio
    """Callback function for greenhouse activity log updates."""
    print(f"Received greenhouse log update: {data}")
    with db.app.app_context():
        try:
            greenhouse_log = GreenHouseActivityLogs.query.get(data['log_id'])
            if greenhouse_log:

                greenhouse_log_data = {
                    "log_id": greenhouse_log.log_id,
                    "login_id": greenhouse_log.login_id,
                    "greenhouse_id": greenhouse_log.greenhouse_id,
                    "logs_description": greenhouse_log.logs_description,
                    "log_date": greenhouse_log.log_date.strftime("%Y-%m-%d %H:%M:%S")

                }
                socketio.emit('greenhouse_logs_update', greenhouse_log_data)  # socket

            else:
                print(f"Greenhouse activity log record {data['log_id']} not found.")

        except Exception as e:
            print(f"Error fetching/updating greenhouse activity log: {e}")


def hardware_components_logs_update_callback(data, db, socketio): # Add db and socketio
    """Callback function for hardware components activity log updates."""
    print(f"Received hardware components log update: {data}")
    with db.app.app_context():
        try:
            hardware_components_log = HardwareComponentActivityLogs.query.get(data['log_id'])#get updated. changes in table. by id changes/data.

            if hardware_components_log: # Make , Validation for,. and if,. new log ID, updates
                # Logs record ID/key: Logs  via, mapping via object and Key , logs new changes records: to `log , Id `. updates record changes from Log , Hardwars table changes:
                hardware_components_log_data = { # logs Structure:
                    "log_id": hardware_components_log.log_id,  #update the value : logid , and Logs Id, to: socket. io , sent,. on:., updates data ,., socket Listener and Updates and assign : Log Id changes: update, , logs activities, harvest component, logs and,. from
                    "login_id": hardware_components_log.login_id,#Log user. id. /admin/ id, or
                    "component_id": hardware_components_log.component_id,   #Component, ID,. from Logs,.. log harvest Component:. updates, log activity/hardware logs., updates by Log Id/ and
                    "logs_description": hardware_components_log.logs_description,  #logs description in harvest Log Component models.  update,. any Log id Changes : log activities if updated/exist / changes. any, : to LOG harvest components: any activities related log. tables harvest , component records
                    "log_date": hardware_components_log.log_date.strftime("%Y-%m-%d %H:%M:%S"), # Formatted Readable. logs/activities,.
                }# No Need other table Relation / APIs., for, access , or Read, other Entity via Users., via
                # SO we can logs updates by read directly to,. model table id Log changes only of, harvest, Components Log Activities: .  table, for, logs record. any data activities,. Logs for hardwarecomponentsLog activities / data tables :

                socketio.emit('hardware_components_logs_update', hardware_components_log_data)# FLask,. BE Socket,.IO : call,. and to : , listener if there, change trigger event from
                #via,.. NOTIFY.,  Listen/.Notify Postgress : change. socket changes , broadcast sent BE server,. to, Frontend update data from  models /` logs `,... changes., /
            else:  # check logs
                print(f"Hardware components activity log record {data['log_id']} not found.") #logs error debugging/. found if,. Exisiting,.

        except Exception as e:
            print(f"Error fetching/updating hardware components activity log: {e}")


def hardware_status_logs_update_callback(data, db, socketio):# Add db and socketio
    """Callback function for hardware status activity log updates."""
    print(f"Received hardware status log update: {data}") #log,. checks: check if
    with db.app.app_context():
        try:
            hardware_status_log = HardwareStatusActivityLogs.query.get(data['log_id'])# get  new chagnes , after  updated record by changes to `logs hardwars. and get  its new id log changes / update of via. `id changes after updated/
            if hardware_status_log:#if exisiting., validate/ new changes :
                hardware_status_log_data = { # Map / struct new,. updated record log to via : this Keys for logs and data, logs update
                    "log_id": hardware_status_log.log_id,#,. HardwareStatusLogs., new Updated Logs record,. change  after Insert  changes from Database Operation on. HarvestStatus,.logs new change,.. logs update and Log data to be  .,. via `Log ID record : `. values logs ,
                    "component_id": hardware_status_log.component_id, #Log changes Component, id,.. Hardward changes logs of current if changes : for activieis `LOG models`

                    "greenhouse_id": hardware_status_log.greenhouse_id,#GH Changes
                    "status": hardware_status_log.status,  #Logs status and data logs/activities records changes , updates /insert / changes  ,. from hardward status change `for current model : logs /` models table log activity / via,  hardware model/status log record : new update., Log id ` after update from DB CURD database opertaions. changes via CURD, log record `and updates by new, ` values and Keys , for log ID from , harvestStatus and new value :` of tables and record. logs and new values and changes by logs from harvest-current-status/ table log change activity.
                    "duration": hardware_status_log.duration,  #data , updates, change after trigger/updates on:.. to Logs activity changes any Log
                    "timestamp": hardware_status_log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                }# SO, dont need any access. other Entity. relationship or., Access. `directly models` by its `itself to logs record/ and sent changes/new changes. to,. the: via  Log Ids  it., only for,. hardwareStatus models  of record change ,. via ID to :. make update for
                # logs , id updates via: : activity.,,. Logs Harvest logs models activity, via `callbacks., socket`. listener events broadcast sent
                socketio.emit('hardware_status_logs_update', hardware_status_log_data)
            else:# Error ID during., id logs changes/update. , harvest,. if exist the  id logs /updates/  record in /Logs
                print(f"Hardware status activity log record {data['log_id']} not found.")

        except Exception as e:
            print(f"Error fetching/updating hardware status activity log: {e}")


def harvest_logs_update_callback(data, db, socketio):  # Add db and socketio
    """Callback function for harvest activity log updates."""
    print(f"Received harvest log update: {data}")#logs check
    with db.app.app_context():
        try:
            harvest_log = HarvestActivityLogs.query.get(data['log_id'])
            if harvest_log:
                harvest_log_data = {
                    "log_id": harvest_log.log_id, #data new udpates ,. log activities of harvest, logs id and models changes,., after update via logs Id,. and logs /changes.. values , field table via, add  and data add to LOG activity /logs record
                    "login_id": harvest_log.login_id, #log login id : and Logs harvest,.  id log activiti. , values.,., harvest: model activity and  assign data:  , from.,., via models Log, activiti/ logs : changes update from,. after Insert `Record to database of Log. , harvest`
                    "harvest_id": harvest_log.harvest_id,  # get , changes: logs, update in data in., via Logs models,. tables via, activity : `harvest and,  logs id. updated changes log ,/activities  by` tables harvest data,.. for `Harvest changes activities`. to:
                    #changes., tables , changes data /insert update via models `harvest_activities model table logs ` activities and via, Log ID Record CHanges of Logs. from / `
                    "logs_description": harvest_log.logs_description,# log,. updated values, logs changes if updated on log models : harvest , logs harvest change/via id for Harvest table change/ logs if add data in harvests. tables  : log harvest changes for, logsactivities,.  id : tables. logs activitie /new. : record insert logs id: data,. harvestLogs. any insert log,. add ,.. data records , activities , tables changes,  update via  ID , log,. update `from table record models of logs  `.  Logs ID: value of
                    "log_date": harvest_log.log_date.strftime("%Y-%m-%d %H:%M:%S"),#log dat from and. readable.
                } #. ,. harvest-Data.. / , No user  table Api related Access data: can :  and no api used. no call api other:
                socketio.emit('harvest_logs_update', harvest_log_data)# cal via.,.. call: to via , sent.

            else:
                print(f"Harvest activity log record {data['log_id']} not found.")#Logs check: print, not Exist,. changes via input id for check log activity table harvest /changes via, harvest `logs,. records.` data model and make new id

        except Exception as e:# Exception all connection,.. issue/logs report debug check., report message.. if error , issue,. other problems: otherbugs check report and: logs Print exception handling/ errors related., with:.. connection in
            print(f"Error fetching/updating harvest activity log: {e}")



def maintenance_logs_update_callback(data, db, socketio):  # Add db and socketio
    """Callback function for maintenance activity log updates."""
    print(f"Received maintenance log update: {data}")
    with db.app.app_context():
        try:

            maintenance_log = MaintenanceActivityLogs.query.get(data['log_id'])
            if maintenance_log:
                maintenance_log_data = {
                    "log_id": maintenance_log.log_id,#log id logs of, Maintenace records  Logs activities ID if, chnages and sent. update record,.. new added via Insert ,log : models, Log Maintence, after, `maintenance done!` to tables if changed., : , if change ` maintenance Record, , Log maintenance Changes if logs. record maintenance record loges add record, , in activiti Logs

                    "login_id": maintenance_log.login_id,#data new change. id of User and : maintence of , change records , data any activities/changes, after new value added `from the., tables., :
                    "maintenance_id": maintenance_log.maintenance_id, #Maintenenace, Logs Activity,.. Log :., ` via.,.  tables ID of: after. data Change., records insert,. for logs.,/ tables and if chnages Logs Table: change maintenance and via the., maintenance: change, any of models /tables after` Record update./ data change / any chage / data add maintenance and.. will make new,. log
                    #data/records maintenance , update in maintenances logs if any. Record data via maintenanc and add,.. or,. any maintena
                    "logs_description": maintenance_log.logs_description,#logsDescription,. and , changes Logs Record from Activities Table , via model logs Id maintenances change: tables. for log,., and, change if : Log has,.. chagnes activities of. id any, logs for,. maintenacelog models : log maintenances if change
                    "log_date": maintenance_log.log_date.strftime("%Y-%m-%d %H:%M:%S"),#Formatted. the logs activiti , via,.. Readble : of Date format string. logs: if maintenance changes for logs to, date: to, Readable and for dates, string

                    "name": maintenance_log.name, # Maintenance name , change
                }
                socketio.emit('maintenance_logs_update', maintenance_log_data) # Sent updates if  there Changes record., log Id for `logs , maintenance table / change on

            else:#If Log Id no records / Invalid
                print(f"Maintenance activity log record {data['log_id']} not found.")

        except Exception as e:  # Catch all errors. related if the Database problem Issue. will Raise Exceptions. here/ other problem if
            print(f"Error fetching/updating maintenance activity log: {e}") # report /log error




def nutrient_controller_logs_update_callback(data, db, socketio): # Add db and socketio parameters
    """Callback function for nutrient controller activity log updates."""
    print(f"Received nutrient controller log update: {data}")#Debug Print Logs check Reciever
    with db.app.app_context():
        try:
            nutrient_controller_log = NutrientControllerActivityLogs.query.get(data['log_id'])  #get by log_id from  updated change of after added  from nutrients model and., and: any log change,. in controllerlog record. change

            if nutrient_controller_log:  #If Valid and found Change on Records of Activities Models tables and new changes on : Log ID value/update,. changes in `data tables model / after., updated record via id: from. nutrient tables:`
                nutrient_controller_log_data = {# data /structures: /: logs  records.,  new,. : records update
                    "log_id": nutrient_controller_log.log_id,#assign logs nutrient update id ,.. ,
                    "controller_id": nutrient_controller_log.controller_id,#Data Nutrients change `  logs and if, updates after any chnages on the Models NutrientControllerLog after, : data tables change in nutrient. tables change id `after new data change via table: for logs models /table., any,. udpates or : changes /add via:  log nutrient controller
                    "logs_description": nutrient_controller_log.logs_description, #Log. , Descriptions if logs nutrient via new logs ID changes of Log table

                    "greenhouse_id": nutrient_controller_log.greenhouse_id,   # updates log activities and record,. for tables any change , if logs data/id to,.. added,  , changes values change in, any log `add`/records add/update
                    "activated_by": nutrient_controller_log.activated_by, #  updated: changes on Log  id models /logs data tables and : of via: `changes tables  `via  `updates via., logid: change
                    #from
                    "logs_date": nutrient_controller_log.logs_date.strftime("%Y-%m-%d %H:%M:%S")#Format Log
                }
                socketio.emit('nutrient_controller_logs_update', nutrient_controller_log_data)#emit changes

            else:# NO id/record
                print(f"Nutrient controller activity log record {data['log_id']} not found.") #error check and debug if id valid to make/and change Logs of Nutrient models record: of

        except Exception as e:
            print(f"Error fetching/updating nutrient controller activity log: {e}")#Exceptions any database,. issue error : Report error to:.. /bugs,. Report error


def rejection_logs_update_callback(data, db, socketio): # Add db and socketio parameters
    """Callback function for rejection activity log updates."""
    print(f"Received rejection log update: {data}")
    with db.app.app_context():
        try:
            rejection_log = RejectionActivityLogs.query.get(data['log_id'])
            if rejection_log:
                rejection_log_data = {
                    "log_id": rejection_log.log_id,# logs  log Reject., changes : `records,.
                    "login_id": rejection_log.login_id, # users ID., rejection/ models data records., changes via add log id table,. if log id , added. or inserted `records, value from,. : LOG changes,.. Rejection new added Logs. ID of models table,. activities records updates`.. by  if changes ` Logs Id activities Rejections models, added.. . reject models if added.. data record logs, reject,.. .  after ,.` REjected `
                    # record inserted
                    "rejection_id": rejection_log.rejection_id,# New Reject, new Change,. rejected after sent logs Reject,. after  , to: Logs
                    # log `Reject., ID rejection Logs,.
                    "logs_description": rejection_log.logs_description,   # Log description , `update the table Rejected Logs `
                    "log_date": rejection_log.log_date.strftime("%Y-%m-%d %H:%M:%S"), #readable Date string, and: dates on :., and to convert string and  Logs Rejected and Format to string.,,logs , models any Log Rejection: and
                   # No,.. used api or, call table, from data/ or via tables logs reject / changes by ` rejected/model/,. data ` : change in.. , table data. on Log Rejected tables via,. add , it., itself :
                }#SO logs Rejected activities Log via id :
                socketio.emit('rejection_logs_update', rejection_log_data) # and FIre socket broadcast  if any changes of Logs Rejectiactivities: and Call and event,. broadcast sent if theresa a and logs table. records and changes:.,
                    # to REJECTED `logs/activities tables: ` .
            else:
                print(f"Rejection activity log record {data['log_id']} not found.")#debugging id., found, ` rejected Record Changes LOG ` data no valid, not

        except Exception as e:# check and if, have problems
            print(f"Error fetching/updating rejection activity log: {e}")# Logs for Erros issue debug and,. connections `database :
