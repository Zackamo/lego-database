'''
    api.py
    for the lego webapp project
    Zack Johnson, 17 November 2021

    Flask API to support the lego web application.
    Based on a template by Jeff Ondich
'''
import sys
import flask
import json
import config
import psycopg2

api = flask.Blueprint('api', __name__)

def get_connection():
    ''' Returns a connection to the database described in the
        config module. May raise an exception as described in the
        documentation for psycopg2.connect. '''
    return psycopg2.connect(database=config.database,
                            user=config.user,
                            password=config.password)

@api.route('/sets/')
def get_sets():
    ''' Returns a list of LEGO sets in json form corresponding to the GET arguments
            search_for, str: only find sets with names LIKE %search_string%
            theme, int: only return sets with the given theme id
            sort_by, str: sets the psql column to sort by
            order, str: 'asc' or 'desc' the latter adds the DESC command
        if GET parameters are absent, return an arbitrary subset of the list of sets
    '''
    search_string = flask.request.args.get('search_for', default='').lower()
    theme = flask.request.args.get('theme', default='')
    sort_by = flask.request.args.get('sort_by', default='')
    order = flask.request.args.get('order', default='asc')

    # the sub-select statement creates a table of sets and total number of figures in that set.
    # it explicitly includes sets with no figures which would otherwise be excluded by a WHERE clause.
    query = '''SELECT sets.set_num, sets.name, themes.name, sets.num_parts, SUM(sets_num_minifigs.quantity) AS num_figs, sets.year
            FROM sets, themes, inventories,
                (SELECT inventories.id, 0 as quantity
                FROM inventories
                WHERE inventories.id NOT IN (SELECT inventory_id FROM inventory_minifigs)
                UNION
                SELECT inventories.id, inventory_minifigs.quantity
                FROM inventories, inventory_minifigs
                WHERE inventories.id = inventory_minifigs.inventory_id) sets_num_minifigs
            WHERE sets.theme_id = themes.id
            AND sets.set_num = inventories.set_num
            AND sets_num_minifigs.id = inventories.id
            AND LOWER(sets.name) LIKE %s
            '''
    input_tuple = ('%' + search_string + '%',)
    if (theme != ''):
        input_tuple += (theme,)
        query += ' AND sets.theme_id = %s '
    query += ''' GROUP BY sets.set_num, sets.name, themes.name, sets.num_parts, sets.year
    HAVING sets.num_parts > 1'''

    set_headers = ['sets.set_num', 'sets.name', 'themes.name', 'sets.num_parts', 'num_figs', 'sets.year']
    try:
        sort_by = int(sort_by)
    except:
        sort_by = -1
    order_by_string = ''
    if (sort_by >= 0 and sort_by < len(set_headers)):
        order_by_string = ' ORDER BY ' + set_headers[sort_by]
        if (order == 'desc'):
            order_by_string += ' DESC '
    query += order_by_string
    query += ';'

    sets_list = []
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(query, input_tuple)
        for row in cursor:
            set = {'set_num':row[0],
                      'name':row[1],
                      'theme':row[2],
                      'num_parts':row[3],
                      'num_figs':row[4],
                      'year':row[5]}
            sets_list.append(set)
        cursor.close()
        connection.close()
    except Exception as e:
        print(e, file=sys.stderr)

    return json.dumps(sets_list)

@api.route('/minifigs/')
def get_minifigs():
    ''' Returns a list of LEGO Minifigures in json form corresponding to the GET arguments
            search_for, str: only find figures with names LIKE %search_string%
            sort_by, str: sets the psql column to sort by
            order, str: 'asc' or 'desc'. the latter adds the DESC command.
            theme, int: only return minifigs with at least one set in the given theme
        if GET parameters are absent, return an arbitrary subset of the list of minifigures.
    '''
    search_string = flask.request.args.get('search_for', default='').lower()
    sort_by = flask.request.args.get('sort_by', default='-1')
    order = flask.request.args.get('order', default='asc')
    theme = flask.request.args.get('theme', default='')

    input_tuple = ('%'+ search_string +'%',)
    # additional tables are needed to find minifigs by theme so I used a seperate query
    if (theme != ''):
        query = '''SELECT minifigs.fig_num, minifigs.name, minifigs.num_parts, COUNT(DISTINCT inventories.set_num) AS sets_in
                FROM minifigs, inventories, inventory_minifigs, sets
                WHERE minifigs.fig_num = inventory_minifigs.fig_num
                AND inventory_minifigs.inventory_id = inventories.id
                AND inventories.set_num = sets.set_num
                AND LOWER(minifigs.name) LIKE %s
                AND sets.theme_id = %s
                GROUP BY minifigs.fig_num, minifigs.name, minifigs.num_parts'''
        input_tuple += (theme,)
    else:
        query = '''SELECT minifigs.fig_num, minifigs.name, minifigs.num_parts, COUNT(DISTINCT inventories.set_num) AS sets_in
                FROM minifigs, inventories, inventory_minifigs
                WHERE minifigs.fig_num = inventory_minifigs.fig_num
                AND inventory_minifigs.inventory_id = inventories.id
                AND LOWER(minifigs.name) LIKE %s
                GROUP BY minifigs.fig_num, minifigs.name, minifigs.num_parts'''

    order_by_string = ''
    fig_headers = ['minifigs.fig_num', 'minifigs.name', 'minifigs.num_parts', 'sets_in']
    try:
        sort_by = int(sort_by)
    except:
        sort_by = -1
    if (sort_by >= 0 and sort_by < len(fig_headers)):
        order_by_string = ' ORDER BY '
        order_by_string += fig_headers[sort_by]
        if (order == 'desc'):
            order_by_string += ' DESC '
    query += order_by_string
    query += ';'

    minifig_list = []
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(query, input_tuple)
        for row in cursor:
            minifig = {'fig_num':row[0],
                      'name':row[1],
                      'num_parts':row[2],
                      'num_sets':row[3]}
            minifig_list.append(minifig)
        cursor.close()
        connection.close()
    except Exception as e:
        print(e, file=sys.stderr)

    return json.dumps(minifig_list)

@api.route('/help/')
def get_help():
    help_text = open('templates/help.txt').read()
    return flask.Response(help_text, mimetype='text/plain')
