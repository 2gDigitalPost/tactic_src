###########################################################
#
# Copyright (c) 2005, Southpaw Technology
#                     All Rights Reserved
#
# PROPRIETARY INFORMATION.  This software is proprietary to
# Southpaw Technology, and is not to be reproduced, transmitted,
# or disclosed in any way without written permission.
#
#
#

__all__ = ["EmailHandler", 'OrderInsertedEmail', 'OrderEditedEmail', 'NoteSender', 'MovementInfoSender', 'EquipmentInserted','TaskAssignEmailHandler', 'NoteEmailHandler', 'GeneralNoteEmailHandler', 'GeneralPublishEmailHandler','TaskStatusEmailHandler', 'SubmissionStatusEmailHandler', 'SubmissionEmailHandler', 'SubmissionNoteEmailHandler', 'TestEmailHandler'] #MTM added classes here

from pyasm.common import Environment, Xml, Date
from pyasm.security import Login, LoginGroup, Sudo
from pyasm.search import Search, SObject, SearchType
from pyasm.biz import GroupNotification, Pipeline, Task, Snapshot, File, Note
from pyasm.biz import ExpressionParser


class EmailHandler(object):
    '''Base class for email notifications'''

    def __init__(my, notification, sobject, parent, command, input):
        my.notification = notification
        my.sobject = sobject
        my.command = command
        my.parent = parent
        my.input = input

    def check_rule(my):
        '''determine whether an email should be sent'''
        return True
        


    def get_mail_users(my, column):
        # mail groups
        recipients = set()

        expr = my.notification.get_value(column, no_exception=True)
        if expr:
            sudo = Sudo()
            # Introduce an environment that can be reflected
            env = {
                'sobject': my.sobject
            }

            #if expr.startswith("@"):
            #    logins = Search.eval(expr, list=True, env_sobjects=env)
            #else:
            parts = expr.split("\n")

            # go through each login and evaluate each
            logins = []
            for part in parts:
                if part.startswith("@") or part.startswith("{"):
                    results = Search.eval(part, list=True, env_sobjects=env)
                    # clear the container after each expression eval
                    ExpressionParser.clear_cache()
                    # these can just be login names, get the actual Logins
                    if results:
                        if isinstance(results[0], basestring):
                            login_sobjs = Search.eval("@SOBJECT(sthpw/login['login','in','%s'])" %'|'.join(results),  list=True)
                        
                            login_list = SObject.get_values(login_sobjs, 'login')
                            
                            for result in results:
                                # the original result could be an email address already
                                if result not in login_list:
                                    logins.append(result)
                                
                            if login_sobjs:
                                logins.extend( login_sobjs )
                        else:
                            logins.extend(results)

                elif part.find("@") != -1:
                    # this is just an email address
                    logins.append( part )
                elif part:
                    # this is a group
                    group = LoginGroup.get_by_code(part)
                    if group:
                        logins.extend( group.get_logins() )

            del sudo
        else:
            notification_id = my.notification.get_id()
            logins = GroupNotification.get_logins_by_id(notification_id)

        for login in logins:
            recipients.add(login) 

        return recipients


    def get_to(my):
        return my.get_mail_users("mail_to")

    def get_cc(my):
        return my.get_mail_users("mail_cc")

    def get_bcc(my):
        return my.get_mail_users("mail_bcc")


    def get_subject(my):
        subject = my.notification.get_value("subject",no_exception=True)
        if subject:
            # parse it through the expression
            sudo = Sudo()
            parser = ExpressionParser()
            subject  = parser.eval(subject, my.sobject, mode='string')
            del sudo
        else:
            subject = '%s - %s' %(my.sobject.get_update_description(), my.command.get_description())
        return subject


    def get_message(my):
        search_type_obj = my.sobject.get_search_type_obj()
        title = search_type_obj.get_title()
        subject = my.get_subject()
        notification_message = my.notification.get_value("message")
        if notification_message:
            # parse it through the expression
            sudo = Sudo()
            parser = ExpressionParser()
            snapshot = my.input.get('snapshot')
            env_sobjects = {}

            # turn prev_data and update_data from input into sobjects
            prev_data = SearchType.create("sthpw/virtual")
            id_col = prev_data.get_id_col()

            if id_col:
                del prev_data.data[id_col]

            for name, value in my.input.get("prev_data").items():
                if value != None:
                    prev_data.set_value(name, value)


            update_data = SearchType.create("sthpw/virtual")
            id_col = update_data.get_id_col()

            if id_col:
                del update_data.data[id_col]

            for name, value in my.input.get("update_data").items():
                if value != None:
                    update_data.set_value(name, value)



            if snapshot:

                env_sobjects = {
                'snapshot': snapshot
            }


            env_sobjects['prev_data'] = prev_data
            env_sobjects['update_data'] = update_data

            notification_message  = parser.eval(notification_message, my.sobject, env_sobjects=env_sobjects, mode='string')
            del sudo
            return notification_message

        message = "%s %s" % (title, my.sobject.get_name())
        message = '%s\n\nReport from transaction:\n%s\n' % (message, subject)
        return message

class OrderInsertedEmail(EmailHandler): # MTM added this whole class
    def _get_login(my, assigned):
        return Login.get_by_login(assigned)

    def get_mail_users(my, column):
        # mail groups
        recipients = set()
        sob = my.sobject
        client_email_list = sob.get_value('client_email_list')
        split = client_email_list.split(',')
        for sp in split:
            recipients.add(sp)
        return recipients

    def get_cc(my):
        print "MY.GET_MAIL_USERS MAIL CC = %s" % my.get_mail_users("mail_cc")
        return my.get_mail_users("mail_cc")

    def kill_none(my, in_str):
        out_str = ''
        if in_str != None:
            out_str = in_str
        return out_str

    def get_subject(my):
        from tactic_client_lib import TacticServerStub
        server = TacticServerStub.get()
        order = my.sobject
        client_code = my.kill_none(order.get_value('client_code'))
        order_code = order.get_code()
        order_name = my.kill_none(order.get_value('name'))
        client_login = my.kill_none(order.get_value('client_login')) 
        if client_login == '':
            client_login = my.kill_none(order.get_value('login'))
        client_name = 'NO CLIENT CODE' 
        if client_code not in [None,'']:
            client = server.eval("@SOBJECT(twog/client['code','%s'])" % client_code)
            if client:
                client = client[0]
                client_name = my.kill_none(client.get('name'))
     
        subject = 'New Order for %s [%s]: %s [%s]' % (client_name, client_login, order_name, order_code)
        return subject

    def get_message(my):
        from tactic_client_lib import TacticServerStub
        server = TacticServerStub.get()
        order = my.sobject
        client_code = my.kill_none(order.get_value('client_code'))
        order_code = order.get_code()
        order_name = my.kill_none(order.get_value('name'))
        order_login = my.kill_none(order.get_value('login'))
        po_number = my.kill_none(order.get_value('po_number'))
        client_login = my.kill_none(order.get_value('client_login')) 
        clogin = server.eval("@SOBJECT(sthpw/login['login','%s'])" % client_login)
        is_external = False
        if clogin:
            clogin = clogin[0]
            if clogin.get('location') == 'external':
                is_external = True
        if client_login == '':
            client_login = my.kill_none(order.get_value('login'))
            
        client_name = 'NO CLIENT CODE' 
        if client_code not in [None,'']:
            client = server.eval("@SOBJECT(twog/client['code','%s'])" % client_code)
            if client:
                client = client[0]
                client_name = my.kill_none(client.get('name'))
     
        subject = 'New Order for %s [%s]: %s [%s]' % (client_name, client_login, order_name, order_code)
        msg = []
        msg.append("[%s]" % subject)
        welcome1 = "A New Order has been added by "
        if is_external:
            welcome1 = '%s %s [%s]' % (welcome1, client_login, 'external') 
        else:
            welcome1 = '%s %s [%s]' % (welcome1, order_login, 'internal')
        msg.append(welcome1)
        msg.append("Client: %s" % client_name)
        msg.append("Client Login: %s" % client_login)
        msg.append("Name: %s" % order_name)
        msg.append("PO Number: %s" % po_number)
        msg.append("Classification: %s" % my.kill_none(order.get_value('classification')))
        msg.append("Start Date: %s" % my.kill_none(order.get_value('start_date')))
        msg.append("Due Date: %s" % my.kill_none(order.get_value('due_date')))
        msg.append("Description: %s" % my.kill_none(order.get_value('description')))
        return "\n".join(msg)

class OrderEditedEmail(EmailHandler): # MTM added this whole class

    def init(my):
        my.prev_data = None
        my.prev_data_arr = None

    def _get_login(my, assigned):
        return Login.get_by_login(assigned)

    def get_mail_users(my, column):
        # mail groups
        recipients = set()
        sob = my.sobject
        client_email_list = sob.get_value('client_email_list')
        split = client_email_list.split(',')
        for sp in split:
            recipients.add(sp)
        return recipients

    def get_cc(my):
        print "MY.GET_MAIL_USERS MAIL CC = %s" % my.get_mail_users("mail_cc")
        return my.get_mail_users("mail_cc")

    def kill_none(my, in_str):
        out_str = ''
        if in_str != None:
            out_str = in_str
        return out_str

    def get_subject(my):
        from tactic_client_lib import TacticServerStub
        from pyasm.common import Environment
        login_obj = Environment.get_login()
        login = login_obj.get_login()
        server = TacticServerStub.get()
        order = my.sobject
        my.prev_data = order.get_prev_update_data()
        print "ORDER STUFF = %s" % order
        prev_data = my.prev_data
        print "PREV DATA STUFF = %s" % prev_data
        my.prev_data_arr = prev_data.keys()
        prev_data_str = ''
        for pd in my.prev_data_arr:
            if prev_data_str == '':
                prev_data_str = "'%s'" % pd
            else:
                prev_data_str = "%s,'%s'" % (prev_data_str, pd)
        prev_data_str = "[%s]" % prev_data_str
        print "STOP 1"
        client_code = my.kill_none(order.get_value('client_code'))
        print "STOP 2"
        order_code = order.get_code()
        order_name = my.kill_none(order.get_value('name'))
        client_login = my.kill_none(order.get_value('client_login')) 
        if client_login == '':
            client_login = my.kill_none(order.get_value('login'))
        client_name = 'NO CLIENT CODE' 
        if client_code not in [None,'']:
            client = server.eval("@SOBJECT(twog/client['code','%s'])" % client_code)
            if client:
                client = client[0]
                client_name = my.kill_none(client.get('name'))
     
        subject = 'Order Edited %s by %s: %s [%s]' % (prev_data_str, login, order_name, order_code)
        #subject = 'Order Edited By Client %s [%s]: %s [%s]' % (client_name, login, order_name, order_code)
        return subject

    def get_message(my):
        from tactic_client_lib import TacticServerStub
        from pyasm.common import Environment
        login_obj = Environment.get_login()
        login = login_obj.get_login()
        server = TacticServerStub.get()
        order = my.sobject
        print "ORDER STUFF = %s" % order
        prev_data = my.prev_data
        print "PREV DATA STUFF = %s" % prev_data
        update_desc = my.sobject.get_update_description()
        client_code = my.kill_none(order.get_value('client_code'))
        order_code = order.get_code()
        order_name = my.kill_none(order.get_value('name'))
        order_login = my.kill_none(order.get_value('login'))
        po_number = my.kill_none(order.get_value('po_number'))
        client_login = my.kill_none(order.get_value('client_login')) 
        clogin = server.eval("@SOBJECT(sthpw/login['login','%s'])" % client_login)
        is_external = False
        if clogin:
            clogin = clogin[0]
            if clogin.get('location') == 'external':
                is_external = True
        if client_login == '':
            client_login = my.kill_none(order.get_value('login'))
            
        client_name = 'NO CLIENT CODE' 
        if client_code not in [None,'']:
            client = server.eval("@SOBJECT(twog/client['code','%s'])" % client_code)
            if client:
                client = client[0]
                client_name = my.kill_none(client.get('name'))
        changes_str = ''
        print "MSG PREV DATA ARR = %s" % my.prev_data_arr
        for pd in my.prev_data_arr:
            old_data = prev_data.get(pd)
            new_data = order.get_value(pd)
            print "%s: Old = %s, New = %s" % (pd, old_data, new_data)
            if new_data != old_data:
                if changes_str == '':
                    changes_str = '%s\nOld Data: %s\nNew Data: %s\n' % (pd, old_data, new_data)
                else:
                    changes_str = '%s\n%s\nOld Data: %s\nNew Data: %s\n' % (changes_str, pd, old_data, new_data)
     
        #subject = 'Order Edited By Client %s [%s]: %s [%s]' % (client_name, login, order_name, order_code)
        msg = []
        #msg.append("[%s]" % subject)
        welcome1 = "Order [po: %s] has been edited by " % po_number
        if is_external:
            welcome1 = '%s %s [%s]' % (welcome1, client_login, 'external') 
        else:
            welcome1 = '%s %s [%s]' % (welcome1, order_login, 'internal')
        msg.append(welcome1)
        msg.append("Client: %s" % client_name)
        msg.append("Client Login: %s" % client_login)
        msg.append("Name: %s" % order_name)
        msg.append("PO Number: %s" % po_number)
        msg.append("Classification: %s" % my.kill_none(order.get_value('classification')))
        msg.append("Start Date: %s" % my.kill_none(order.get_value('start_date')))
        msg.append("Due Date: %s" % my.kill_none(order.get_value('due_date')))
        #msg.append("Description: %s" % my.kill_none(order.get_value('description')))
        msg.append("\nChanges:\n%s" % changes_str)
        #msg.append(update_desc)
        return "\n".join(msg)

class NoteSender(EmailHandler): # MTM added this whole class
    def _get_login(my, assigned):
        return Login.get_by_login(assigned)

    def get_subject(my):
        from tactic_client_lib import TacticServerStub
        server = TacticServerStub.get()
        note = my.sobject
        print "NOTE = %s" % note
        parent = note.get_parent()
        print "PARENT = %s" % parent
        code = parent.get_code()
        print "CODE = %s" % code
        work_order = None
        proj = None
        title = None
        order = None
        if 'WORK_ORDER' in code:
            work_order = server.eval("@SOBJECT(twog/work_order['code','%s'])" % code)[0]
            proj = server.eval("@SOBJECT(twog/proj['code','%s'])" % work_order.get('proj_code'))[0]
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % proj.get('title_code'))[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        elif 'PROJ' in code:
            proj = server.eval("@SOBJECT(twog/proj['code','%s'])" % code)[0]
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % proj.get('title_code'))[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        elif 'TITLE' in code:
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % code)[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        elif 'ORDER' in code:
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % code)[0]
        note_code = note.get_code()
        parent_code = code
        po_number = ''
        order_name = ''
        title_title = ''
        title_episode = ''
    
        if order: 
            po_number = order.get('po_number')
            order_name = order.get('name')
        if title:
            title_title = title.get('title')
            title_episode = title.get('episode')
     
        subject = '%s(%s) - %s: %s - %s for %s' % (order_name, po_number, title_title, title_episode, note_code, parent_code)
        return subject

    def kill_none(my, in_str):
        out_str = ''
        if in_str != None:
            out_str = in_str
        return out_str

    def get_message(my):
        from tactic_client_lib import TacticServerStub
        server = TacticServerStub.get()
        note = my.sobject
        parent = note.get_parent()
        code = parent.get_code()
        work_order = None
        proj = None
        title = None
        order = None
        if 'WORK_ORDER' in code:
            work_order = server.eval("@SOBJECT(twog/work_order['code','%s'])" % code)[0]
            proj = server.eval("@SOBJECT(twog/proj['code','%s'])" % work_order.get('proj_code'))[0]
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % proj.get('title_code'))[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        elif 'PROJ' in code:
            proj = server.eval("@SOBJECT(twog/proj['code','%s'])" % code)[0]
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % proj.get('title_code'))[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        elif 'TITLE' in code:
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % code)[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        elif 'ORDER' in code:
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % code)[0]
        note_code = note.get_code()
        parent_code = code
        po_number = ''
        order_name = ''
        title_title = ''
        title_episode = ''
    
        msg = []
        if order: 
            po_number = my.kill_none(order.get('po_number'))
            order_name = my.kill_none(order.get('name'))
        if title:
            title_title = my.kill_none(title.get('title'))
            title_episode = my.kill_none(title.get('episode'))
     
        subject = '%s(%s) - %s: %s - %s for %s' % (order_name, po_number, title_title, title_episode, note_code, parent_code)
        print "SUBJECT = %s" % subject
        msg.append("[%s]" % subject)
        print "MSG = %s" % msg
        if order:
            order_name = my.kill_none(order.get('name'))
            po_number = my.kill_none(order.get('po_number'))
            order_code = my.kill_none(order.get('code'))
            msg.append("Order: %s (%s)  [[%s]]" % (order_name, po_number, order_code))
        if title:
            part = title.get('strat2g_part')
            if part in [None,'']:
                part = title.get('part')
            part = my.kill_none(part)
            msg.append("Title: %s: %s, %s [%s] [[%s]]" % (title_title, title_episode, part, my.kill_none(title.get('barcode')), my.kill_none(title.get('code'))))
        if proj:
            msg.append('Proj: %s [[%s]]' % (my.kill_none(proj.get('process')), my.kill_none(proj.get('code'))))
        if work_order:
            msg.append('Work Order: %s [[%s]], Task Code: %s' % (my.kill_none(work_order.get('process')), my.kill_none(work_order.get('code')), my.kill_none(work_order.get('task_code')))) 
        if msg == []:
            msg.append(code)
        msg.append(" ")
        msg.append("NOTE:")
        msg.append(note.get_value('note').encode('utf-8'))
        return "\n".join(msg)

class MovementInfoSender(EmailHandler): # MTM added this whole class
    #def _get_login(my, assigned):
    #    print "_GET_LOGIN RESULT = %s" % Login.get_by_login(assigned)
    #    return Login.get_by_login(assigned)

    #def get_cc(my):
    #    print "GET CC RESULT = %s" % my.get_mail_users("mail_cc")
    #    return my.get_mail_users("mail_cc")

    def get_subject(my):
        from tactic_client_lib import TacticServerStub
        server = TacticServerStub.get()
        print "SERVER = %s" % server
        movement = my.sobject
        movement_code = movement.get_code()
        movement_name = movement.get_value('name')
        subject = 'New Arrivals: %s' % movement_name
        return subject

    def kill_none(my, in_str):
        out_str = ''
        if in_str != None:
            out_str = in_str
        return out_str

    def get_message(my):
        from tactic_client_lib import TacticServerStub
        server = TacticServerStub.get()
        movement = my.sobject
        movement_code = movement.get_code()
        movement_name = movement.get_value('name')
        atms = server.eval("@SOBJECT(twog/asset_to_movement['movement_code','%s'])" % movement_code)
        msg = []
        sending_comp = movement.get_value('sending_company_code')
        receiving_comp = movement.get_value('receiving_company_code')
        sender = server.eval("@SOBJECT(twog/company['code','%s'])" % sending_comp)
        receiver = server.eval("@SOBJECT(twog/company['code','%s'])" % receiving_comp)
        company_from = ''
        company_to = ''
        if sender:
            sender = sender[0]
            company_from = sender.get('name')
        if receiver:
            receiver = receiver[0]
            company_to = receiver.get('name')
        msg.append('Movement %s: From: %s To: %s\n' % (movement_name, company_from, company_to))
        msg.append('The following assets have arrived:\n')
        for atm in atms:
            source = server.eval("@SOBJECT(twog/source['code','%s'])" % atm.get('source_code'))
            if source:
                source = source[0]
                barcode = source.get('barcode')
                aspect_ratio = source.get('aspect_ratio')
                client_asset_id = source.get('client_asset_id')
                client_code = source.get('client_code')
                client = server.eval("@SOBJECT(twog/client['code','%s'])" % client_code)
                client_name = ''
                if client:
                    client = client[0]
                    client_name = client.get('name') 
                episode = source.get('episode') 
                file_type = source.get('file_type')
                format = source.get('format')
                frame_rate = source.get('frame_rate')
                generation = source.get('generation')
                high_security = source.get('high_security')
                move_in_type = source.get('move_in_type')
                outside_barcodes = server.eval("@SOBJECT(twog/outside_barcode['source_code','%s'])" % source.get('code'))
                ob_str = ''
                for ob in outside_barcodes:
                    if ob_str == '':
                        ob_str = ob.get('barcode')
                    else:
                        ob_str = '%s, %s' % (ob_str, ob.get('barcode'))
                po_number = source.get('po_number')
                season = source.get('season')
                source_type = source.get('source_type')
                standard = source.get('standard')
                title = source.get('title')
                trt = source.get('total_run_time')
                version = source.get('version')
                msg.append(source.get('code'))
                msg.append('---------------------------------------------------------------------------------')
                if high_security:
                    msg.append('\nHIGH SECURITY')
                msg.append('Barcode: %s   \nTitle: %s   \nEpisode: %s   \nSeason: %s   \nVersion: %s' % (barcode, title, episode, season, version))
                msg.append('\nClient: %s   \nClient Asset Id: %s' % (client_name, client_asset_id)) 
                msg.append('\nMove-In Type: %s   \nSource Type: %s   \nFile Type: %s   \nGeneration: %s' % (move_in_type, source_type, file_type, generation))
                msg.append('\nTRT: %s   \nAspect Ratio: %s   \nFormat: %s   \nFrame Rate: %s   \nStandard: %s' % (trt, aspect_ratio, format, frame_rate, standard))
                if ob_str != '':
                    msg.append('\nOutside Barcodes: %s' % ob_str)
                if high_security:
                    msg.append('\nHIGH SECURITY')
                msg.append('---------------------------------------------------------------------------------')
                msg.append('\n')
        msg.append(movement.get_value('description').encode('utf-8'))
        return "\n".join(msg)

class EquipmentInserted(EmailHandler): # MTM added this whole class
    def get_cc(my):
        print "MY GET MAIL USERS MAIL CC = %s" % my.get_mail_users("mail_cc")
        return my.get_mail_users("mail_cc")

    def get_bcc(my):
        print "MY GET MAIL USERS MAIL BCC = %s" % my.get_mail_users("mail_bcc")
        return my.get_mail_users("mail_bcc")

    def get_to(my):
        from tactic_client_lib import TacticServerStub
        from pyasm.common import Environment
        recipients = set()
        to = 'matt.misenhimer@2gdigital.com'
        login_obj = Environment.get_login()
        login = login_obj.get_login()
        server = TacticServerStub.get()
        eq = my.sobject
        wo_code = eq.get_value('work_order_code')
        
        if wo_code not in [None,'']:
            wo = server.eval("@SOBJECT(twog/work_order['code','%s'])" % wo_code)
            if wo:
                wo = wo[0]
                if wo.get('login') != login:
                    the_obj = Login.get_by_code(wo.get('login'))
                    if the_obj:
                        recipients.add(the_obj)
#                    creator_login_obj = server.eval("@SOBJECT(sthpw/login['login','%s'])" % wo.get('login'))
#                    if creator_login_obj:
#                        creator_login_obj = creator_login_obj[0]
#                        #to = creator_login_obj.get('email')
#                        to = creator_login_obj
        print "RETURN Recipients: %s" % recipients        
        return recipients

    def get_subject(my):
        from tactic_client_lib import TacticServerStub
        server = TacticServerStub.get()
        eq = my.sobject
        equipment_name = eq.get_value('name')
        work_order_code = eq.get_value('work_order_code')
        work_order = None
        proj = None
        title = None
        order = None
        if work_order_code not in [None,'']:
            work_order = server.eval("@SOBJECT(twog/work_order['code','%s'])" % work_order_code)[0]
            proj = server.eval("@SOBJECT(twog/proj['code','%s'])" % work_order.get('proj_code'))[0]
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % proj.get('title_code'))[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        po_number = ''
        order_name = ''
        title_title = ''
        title_episode = ''
        proj_code = ''
        if order: 
            po_number = order.get('po_number')
            order_name = order.get('name')
        if title:
            title_title = title.get('title')
            title_episode = title.get('episode')
        if proj:
            proj_code = proj.get('code')
     
        subject = 'Equipment Added by Operator in %s (%s), to %s: %s-%s-%s ' % (order_name, po_number, title_title, title_episode, proj_code, work_order_code)
        return subject

    def kill_none(my, in_str):
        out_str = ''
        if in_str != None:
            out_str = in_str
        return out_str

    def get_message(my):
        from tactic_client_lib import TacticServerStub
        from pyasm.common import Environment
        login_obj = Environment.get_login()
        login = login_obj.get_login()
        server = TacticServerStub.get()
        eq = my.sobject
        eq_code = eq.get_code()
        equip = server.eval("@SOBJECT(twog/equipment_used['code','%s'])" % eq_code)[0]
        equipment_name = equip.get('name')
        work_order_code = equip.get('work_order_code')
        work_order = None
        proj = None
        title = None
        order = None
        if work_order_code not in [None,'']:
            work_order = server.eval("@SOBJECT(twog/work_order['code','%s'])" % work_order_code)[0]
            proj = server.eval("@SOBJECT(twog/proj['code','%s'])" % work_order.get('proj_code'))[0]
            title = server.eval("@SOBJECT(twog/title['code','%s'])" % proj.get('title_code'))[0]
            order = server.eval("@SOBJECT(twog/order['code','%s'])" % title.get('order_code'))[0]
        po_number = ''
        order_name = ''
        title_title = ''
        title_episode = ''
        proj_code = ''
        if order: 
            po_number = order.get('po_number')
            order_name = order.get('name')
        if title:
            title_title = title.get('title')
            title_episode = title.get('episode')
        if proj:
            proj_code = proj.get('code')
     
        subject = 'Equipment Added by Operator in %s (%s), to %s: %s-%s-%s ' % (order_name, po_number, title_title, title_episode, proj_code, work_order_code)
        msg = []
        msg.append(subject)
        if order:
            order_name = my.kill_none(order.get('name'))
            po_number = my.kill_none(order.get('po_number'))
            order_code = my.kill_none(order.get('code'))
            msg.append("Order: %s (%s)  [[%s]]" % (order_name, po_number, order_code))
        if title:
            part = title.get('strat2g_part')
            if part in [None,'']:
                part = title.get('part')
            part = my.kill_none(part)
            msg.append("Title: %s: %s, %s [%s] [[%s]]" % (title_title, title_episode, part, my.kill_none(title.get('barcode')), my.kill_none(title.get('code'))))
            msg.append('Title Pipeline: %s' % title.get('pipeline_code'))
        if proj:
            msg.append('Proj: %s [[%s]]' % (my.kill_none(proj.get('process')), my.kill_none(proj.get('code'))))
            msg.append('Proj Pipeline: %s' % proj.get('pipeline_code'))
        if work_order:
            msg.append('Work Order: %s [[%s]], Task Code: %s' % (my.kill_none(work_order.get('process')), my.kill_none(work_order.get('code')), my.kill_none(work_order.get('task_code')))) 
        if msg == []:
            msg.append(eq_code)
        msg.append(" ")
        msg.append("EQUIPMENT INSERTED by %s:" % login)
        msg.append(eq_code)
        msg.append('Name: %s' % equipment_name)
        msg.append('Estimated Quantity: %s' % equip.get('expected_quantity'))
        msg.append('Units: %s' % equip.get('units'))
        msg.append('Estimated Duration: %s' % equip.get('expected_duration'))

        msg.append('Description: %s' % equip.get('description'))
        
        return "\n".join(msg)


class TaskAssignEmailHandler(EmailHandler):
    '''Email sent when a task is assigned'''

    def get_subject(my):
        
        task = my.sobject

        sobject = task.get_parent()
        name = sobject.get_name()

        assigned = task.get_value("assigned")
        task_process = task.get_value("process")
        task_description = task.get_value("description")

        #title = my.notification.get_description()
        title = "Assignment"

        return "%s: %s to %s (%s) %s"  % (title, name, assigned, task_process, task_description)


    def get_to(my):
        # add the assigned user to the list of users sent.
        recipients = super(TaskAssignEmailHandler, my).get_to()

        task = my.sobject
        assigned = task.get_value("assigned")

        login = Login.get_by_login(assigned)
        if not login:
            Environment.add_warning("Non existent user", "User %s does not exist" % assigned)
            return recipients

        recipients.add(login)

        return recipients


    def get_message(my):

        task = my.sobject
       
        assigned = task.get_value("assigned")
        task_process = task.get_value("process")
        task_description = task.get_value("description")
        status = task.get_value("status")

        search_type = task.get_value("search_type")
        search_id = task.get_value("search_id")

        sobject = Search.get_by_search_key("%s|%s" %(search_type, search_id) )

        search_type_obj = sobject.get_search_type_obj()
        title = search_type_obj.get_title()
        code = sobject.get_code()
        name = sobject.get_name()

        msg = []
        msg.append("The following task has been assigned to '%s':" % assigned)

        msg.append("")
        msg.append("Description: %s" % task_description)
        msg.append("Process: %s" % task_process)
        msg.append("Status: %s" % status)

        msg.append("")
        if name == code:
            msg.append("To %s: %s" % (title, name))
        else:
            msg.append("To %s: %s - (%s)" % (title, name, code))

        if sobject.has_value("description"):
            description = sobject.get_value("description")
            msg.append("\"%s\"" % description)

        return "\n".join(msg)



class NoteEmailHandler(EmailHandler):

    def check_rule(my):
        '''determine whether an email should be sent'''
        return True

    def _get_login(my, assigned):
        return Login.get_by_login(assigned)
        
    

    def get_to(my):
        #recipients = super(NoteEmailHandler, my).get_to()
        recipients = set()
        note = my.sobject

        search = Search(Task)
        search.add_filter('search_type', note.get_value('search_type'))
        search.add_filter('search_id', note.get_value('search_id'))
        # it will get the context if process not found
        search.add_filter('process', note.get_process())
        search.add_filter('project_code',note.get_value('project_code'))
        tasks = search.get_sobjects()
        for task in tasks:
            assigned = my._get_login(task.get_assigned())
            if assigned:
                recipients.add(assigned)
            supe = my._get_login(task.get_supervisor())
            if supe:
                recipients.add(supe)
        return recipients


class GeneralNoteEmailHandler(EmailHandler):

    def check_rule(my):
        '''determine whether an email should be sent'''
        return True

    def _get_login(my, assigned):
        return Login.get_by_login(assigned)
        
    def get_to(my):
        #recipients = super(NoteEmailHandler, my).get_to()
        recipients = set()
        note = my.sobject

        search = Search(Task)
        grand_parent = None
        parent_search_type = note.get_value('search_type')
        if 'prod/submission' in parent_search_type:
            grand_parent = my.parent.get_parent()
        
        search_type = note.get_value('search_type')
        search_id = note.get_value('search_id')
        if grand_parent:
            search_type = grand_parent.get_search_type()
            search_id = grand_parent.get_id()

        search.add_filter('search_type', search_type)
        search.add_filter('search_id', search_id )
        # it will get the context if process not found
        #search.add_filter('process', note.get_process())
        search.add_filter('project_code',note.get_value('project_code'))
        tasks = search.get_sobjects()
        for task in tasks:
            assigned = my._get_login(task.get_assigned())
            if assigned:
                recipients.add(assigned)
            supe = my._get_login(task.get_supervisor())
            if supe:
                recipients.add(supe)
        return recipients

    def get_message(my):
        
        search_type_obj = my.sobject.get_search_type_obj()
        title = search_type_obj.get_title()
        
        notification_message = my.notification.get_value("message")

        message = "%s %s" % (title, my.sobject.get_name())
        if notification_message:
            message = "%s (%s)" %(message, notification_message)

        update_desc = my.sobject.get_update_description()
        parent_search_type = my.sobject.get_value('search_type')
        grand_parent = None
        if 'prod/submission' in parent_search_type:
            parent = Search.get_by_id(parent_search_type, my.sobject.get_value('search_id') )
            snapshot = Snapshot.get_latest_by_sobject(parent, 'publish')
            if snapshot:
                file_name = snapshot.get_file_name_by_type('main')
                update_desc = '%s \n %s \n' %(update_desc, file_name)
            grand_parent = parent.get_parent()
            if grand_parent:
                update_desc = '%s %s'%(update_desc, grand_parent.get_code())
        command_desc = my.command.get_description()

        message = '%s\n\nReport from transaction:\n%s\n\n%s' \
            % (message, update_desc, command_desc)
        return message

class GeneralPublishEmailHandler(EmailHandler):
    ''' On publish of a shot/asset, it will find all the assignees of this 
        shot/asset and send the notification to them'''

    def check_rule(my):
        '''determine whether an email should be sent'''
        return True

    def _get_login(my, assigned):
        return Login.get_by_login(assigned)
        
    def get_to(my):
        recipients = super(GeneralPublishEmailHandler, my).get_to()
        sobj = my.sobject

        search = Search(Task)
        
        search_type = sobj.get_search_type()
        
        search_id = sobj.get_id()
       
        search.add_filter('search_type', search_type)
        search.add_filter('search_id', search_id )
        # it will get the context if process not found
        #search.add_filter('process', note.get_process())
        from pyasm.biz import Project
        search.add_filter('project_code', Project.get_project_code())
        tasks = search.get_sobjects()
        for task in tasks:
            assigned = my._get_login(task.get_assigned())
            if assigned:
                recipients.add(assigned)
            supe = my._get_login(task.get_supervisor())
            if supe:
                recipients.add(supe)
        return recipients

    def get_message(my):
        
        search_type_obj = my.sobject.get_search_type_obj()
        title = search_type_obj.get_title()
        
        notification_message = my.notification.get_value("message")

        message = "%s %s" % (title, my.sobject.get_name())
        if notification_message:
            message = "%s (%s)" %(message, notification_message)

        update_desc = my.sobject.get_update_description()
        
        command_desc = my.command.get_description()

        message = '%s\n\nReport from transaction:\n%s\n\n%s' \
            % (message, update_desc, command_desc)
        return message

class TaskStatusEmailHandler(EmailHandler):

    def check_rule(my):
        '''determine whether an email should be sent'''
        return True

    def _get_login(my, assigned):
        return Login.get_by_login(assigned)
        
    def get_to(my):
        recipients = super(TaskStatusEmailHandler, my).get_to()
        sobj = my.sobject
       
        # it could be the parent of task:
        if not isinstance(sobj, Task):
            tasks = Task.get_by_sobject(sobj)
        else:
            tasks = [sobj]

        for task in tasks:
            assigned = my._get_login(task.get_assigned())
            if assigned:
                recipients.add(assigned)
            supe = my._get_login(task.get_supervisor())
            if supe:
                recipients.add(supe)
        return recipients

class SubmissionEmailHandler(EmailHandler):
    '''Email sent when a submission is entered'''

    def get_message(my):
        search_type_obj = my.sobject.get_search_type_obj()
        title = search_type_obj.get_title()
        subject = my.get_subject()
        notification_message = my.notification.get_value("message")

        message = "%s %s" % (title, my.sobject.get_name())
        if notification_message:
            message = "%s (%s)" %(message, notification_message)

        submit_desc = ''

        from pyasm.prod.biz import Submission
        if isinstance(my.sobject, Submission):
            update_info = ['']
            # add more info about the file and bin
            snapshot = Snapshot.get_latest_by_sobject(my.sobject)
            xpath = "snapshot/file[@type='main']"
            if not snapshot:
                return "no snapshot found"
            xml = snapshot.get_xml_value('snapshot')
            file = None
            if xml.get_node(xpath) is not None:
                file = my._get_file_obj(snapshot)
            else:
                snapshots = snapshot.get_all_ref_snapshots()
                snapshot_file_objects = []
                if snapshots:
                    snapshot = snapshots[0]
                    file = my._get_file_obj(snapshot, type=None)
            if file:
                file_name = file.get_file_name()
                web_path = file.get_web_path()
                from pyasm.web import WebContainer 
                host = WebContainer.get_web().get_base_url()
                update_info.append('Browse: %s %s%s' %( file_name, host.to_string(), web_path))

            bins = my.sobject.get_bins()
            bin_labels = [ bin.get_label() for bin in bins]
            update_info.append('Bin: %s' %', '.join(bin_labels))

            update_info.append('Artist: %s' %my.sobject.get_value('artist'))
            update_info.append('Description: %s' %my.sobject.get_value('description'))
             
            # get notes
            search = Note.get_search_by_sobjects([my.sobject])
            if search:
                search.add_order_by("context")
                search.add_order_by("timestamp desc")
            notes = search.get_sobjects()

            last_context = None
            note_list = []
            for i, note in enumerate(notes):
                context = note.get_value('context')
                # explicit compare to None
                if last_context == None or context != last_context:
                    note_list.append( "[ %s ] " % context )
                last_context = context
                
                #child_notes = my.notes_dict.get(note.get_id())
                # draw note item
                date = Date(db=note.get_value('timestamp'))
                note_list.append('(%s) %s'%(date.get_display_time(), note.get_value("note")))
            update_info.append('Notes: \n %s' % '\n'.join(note_list))

            submit_desc =  '\n'.join(update_info)

            
        update_desc = my.sobject.get_update_description()
        command_desc = my.command.get_description()

        message = '%s\n\nReport from transaction:\n%s\n\n%s\n%s' \
            % (message, update_desc, command_desc, submit_desc)
        return message

    def _get_file_obj(my, snapshot, type='main'):
        if type:
            xpath = "snapshot/file[@type='%s']" %type
        else:
            xpath = "snapshot/file[@type]"
        xml = snapshot.get_xml_value('snapshot')
        node = xml.get_node(xpath)
        file = None
        if node is not None:
            file_code = Xml.get_attribute(node, "file_code")
            file = File.get_by_code(file_code)
        return file

class SubmissionStatusEmailHandler(SubmissionEmailHandler):

    def check_rule(my):
        '''determine whether an email should be sent'''
        return True

    def _get_login(my, assigned):
        return Login.get_by_login(assigned)
        
    def get_to(my):
        recipients = super(SubmissionStatusEmailHandler, my).get_to()
        submission = my.sobject
        artist = submission.get_value('artist')
        assigned = my._get_login(artist)
        if assigned:
            recipients.add(assigned)
        
        return recipients

class SubmissionNoteEmailHandler(SubmissionEmailHandler):

    def check_rule(my):
        '''determine whether an email should be sent'''
        return True

    def get_message(my):
        search_type_obj = my.parent.get_search_type_obj()
        title = search_type_obj.get_title()
        subject = my.get_subject()
        notification_message = my.notification.get_value("message")

        message = "%s %s Note Entry" % (title, my.parent.get_name())
        if notification_message:
            message = "%s (%s)" %(message, notification_message)

        submit_desc = ''

        from pyasm.prod.biz import Submission
        if isinstance(my.parent, Submission):
            update_info = ['']
            # add more info about the file and bin
            snapshot = Snapshot.get_latest_by_sobject(my.parent, "publish")
            xpath = "snapshot/file[@type='main']"
            xml = snapshot.get_xml_value('snapshot')
            file = None
            if xml.get_node(xpath) is not None:
                file = my._get_file_obj(snapshot)
            else:
                snapshots = snapshot.get_all_ref_snapshots()
                snapshot_file_objects = []
                if snapshots:
                    snapshot = snapshots[0]
                    file = my._get_file_obj(snapshot, type=None)
            if file:
                file_name = file.get_file_name()
                web_path = file.get_web_path()
                from pyasm.web import WebContainer 
                host = WebContainer.get_web().get_base_url()
                update_info.append('Browse: %s %s%s' %( file_name, host.to_string(), web_path))

            bins = my.parent.get_bins()
            bin_labels = [ bin.get_label() for bin in bins]
            update_info.append('Bin: %s' %', '.join(bin_labels))

            update_info.append('Artist: %s' %my.parent.get_value('artist'))
            update_info.append('Description: %s' %my.parent.get_value('description'))
             
            # get notes
            search = Note.get_search_by_sobjects([my.parent])
            if search:
                search.add_order_by("context")
                search.add_order_by("timestamp desc")
            notes = search.get_sobjects()

            last_context = None
            note_list = []
            for i, note in enumerate(notes):
                context = note.get_value('context')
                # explicit compare to None
                if last_context == None or context != last_context:
                    note_list.append( "[ %s ] " % context )
                last_context = context
                
                #child_notes = my.notes_dict.get(note.get_id())
                # draw note item
                date = Date(db=note.get_value('timestamp'))
                note_list.append('(%s) %s'%(date.get_display_time(), note.get_value("note")))
            update_info.append('Notes: \n %s' % '\n'.join(note_list))

            submit_desc =  '\n'.join(update_info)

            
        update_desc = my.sobject.get_update_description()
        command_desc = my.command.get_description()

        message = '%s\n\nReport from transaction:\n%s\n\n%s\n%s' \
            % (message, update_desc, command_desc, submit_desc)
        return message

        

    def _get_login(my, assigned):
        return Login.get_by_login(assigned)
        
    def get_to(my):
        recipients = super(SubmissionNoteEmailHandler, my).get_to()
        submission = my.parent
        artist = submission.get_value('artist')
        assigned = my._get_login(artist)
        if assigned:
            recipients.add(assigned)
        
        return recipients

class TestEmailHandler(EmailHandler):
    '''Email sent when a task is assigned'''

    def check_rule(my):
        task = my.sobject
       
        assigned = task.get_value("assigned")
        task_process = task.get_value("process")
        task_description = task.get_value("description")

        # get the pipeline
        my.parent = task.get_parent()
        pipeline_code = my.parent.get_value("pipeline_code")
        my.pipeline = Pipeline.get_by_code(pipeline_code)
        if not my.pipeline:
            # No pipeline, so don't email
            print "Warning: No Pipeline"
            return False


        task_status = task.get_value("status")
        if task_status == "Review":
            return True
        else:
            return False



