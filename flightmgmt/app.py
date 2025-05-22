from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import json
import bcrypt


app = Flask(__name__)
app.secret_key = 'your_secret_key_change_in_production'  # Change this to a random string in production

# Database connection function
def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='flight',
            user='root',  # Change to your MySQL username
            password='1234'   # Change to your MySQL password
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error: {e}")
        return None

# Route for the home page
@app.route('/')
def home():
    return render_template('index.html')

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = 'Passenger'  # Default role for new users
        
        # Hash the password with explicit method
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        
        connection = create_connection()
        if connection:
            try:
                cursor = connection.cursor()
                # Check if email already exists
                cursor.execute("SELECT * FROM User WHERE Email = %s", (email,))
                if cursor.fetchone():
                    flash('Email already exists!')
                    return redirect(url_for('register'))
                
                # Insert new user
                cursor.execute(
                    "INSERT INTO User (Name, Email, Password, Role) VALUES (%s, %s, %s, %s)",
                    (name, email, hashed_password, role)
                )
                connection.commit()
                
                flash('Registration successful! Please login.')
                return redirect(url_for('login'))
            except Error as e:
                flash(f"Error: {e}")
            finally:
                if connection.is_connected():
                    cursor.close()
                    connection.close()
        else:
            flash('Database connection failed')
    
    return render_template('register.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        connection = create_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT * FROM User WHERE Email = %s", (email,))
                user = cursor.fetchone()
                
                if user and bcrypt.checkpw(password.encode('utf-8'), user['Password'].encode('utf-8')):

                    # Store user information in session
                    session['user_id'] = user['UserID']
                    session['name'] = user['Name']
                    session['email'] = user['Email']
                    session['role'] = user['Role']
                    
                    if user['Role'] == 'Admin':
                        return redirect(url_for('admin_dashboard'))
                    else:
                        return redirect(url_for('dashboard'))
                else:
                    flash('Invalid email or password')
            except Error as e:
                flash(f"Error: {e}")
            finally:
                if connection.is_connected():
                    cursor.close()
                    connection.close()
        else:
            flash('Database connection failed')
    
    return render_template('login.html')

# Route for user logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Route for user dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    connection = create_connection()
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            # Get user's tickets
            cursor.execute("""
                SELECT t.*, f.Source, f.Destination, f.DepartureTime, f.ArrivalTime, 
                f.Status as FlightStatus, f.FlightID
                FROM Ticket t
                JOIN Flight f ON t.FlightID = f.FlightID
                WHERE t.PassengerID = %s
                ORDER BY f.DepartureTime
            """, (user_id,))
            tickets = cursor.fetchall()
            
            # Get delayed flights for notifications
            delayed_flights = [t for t in tickets if t['FlightStatus'] == 'Delayed']
            
            return render_template('dashboard.html', tickets=tickets, delayed_flights=delayed_flights)
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return render_template('dashboard.html', tickets=[], delayed_flights=[])

# Route for admin dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            # Get all flights
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity, 
                (SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked') as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                ORDER BY f.DepartureTime
            """)
            flights = cursor.fetchall()
            
            return render_template('admin/dashboard.html', flights=flights)
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return render_template('admin/dashboard.html', flights=[])

# Route for adding new flight (admin only)
@app.route('/admin/add_flight', methods=['GET', 'POST'])
def add_flight():
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            # Get all aircraft for dropdown
            cursor.execute("SELECT * FROM Aircraft WHERE MaintenanceStatus = 'Operational'")
            aircraft = cursor.fetchall()
            
            if request.method == 'POST':
                source = request.form['source']
                destination = request.form['destination']
                departure_time = request.form['departure_time']
                arrival_time = request.form['arrival_time']
                aircraft_id = request.form['aircraft_id']
                
                # Insert new flight
                cursor.execute(
                    "INSERT INTO Flight (Source, Destination, DepartureTime, ArrivalTime, AircraftID, Status) VALUES (%s, %s, %s, %s, %s, 'Scheduled')",
                    (source, destination, departure_time, arrival_time, aircraft_id)
                )
                
                connection.commit()
                flash('Flight added successfully!')
                return redirect(url_for('admin_dashboard'))
            
            return render_template('admin/add_flight.html', aircraft=aircraft)
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    return redirect(url_for('admin_dashboard'))

# Route for editing flight (admin only)
@app.route('/admin/edit_flight/<int:flight_id>', methods=['GET', 'POST'])
def edit_flight(flight_id):
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            # Get all aircraft for dropdown
            cursor.execute("SELECT * FROM Aircraft WHERE MaintenanceStatus = 'Operational'")
            aircraft = cursor.fetchall()
            
            # Get flight details
            cursor.execute("SELECT * FROM Flight WHERE FlightID = %s", (flight_id,))
            flight = cursor.fetchone()
            
            if not flight:
                flash('Flight not found')
                return redirect(url_for('admin_dashboard'))
            
            if request.method == 'POST':
                source = request.form['source']
                destination = request.form['destination']
                departure_time = request.form['departure_time']
                arrival_time = request.form['arrival_time']
                aircraft_id = request.form['aircraft_id']
                status = request.form['status']
                
                # Update flight
                cursor.execute(
                    """UPDATE Flight SET 
                    Source = %s, 
                    Destination = %s, 
                    DepartureTime = %s, 
                    ArrivalTime = %s, 
                    AircraftID = %s, 
                    Status = %s 
                    WHERE FlightID = %s""",
                    (source, destination, departure_time, arrival_time, aircraft_id, status, flight_id)
                )
                
                connection.commit()
                flash('Flight updated successfully!')
                return redirect(url_for('admin_dashboard'))
            
            return render_template('admin/edit_flight.html', flight=flight, aircraft=aircraft)
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return redirect(url_for('admin_dashboard'))

# Route for deleting flight (admin only)
@app.route('/admin/delete_flight/<int:flight_id>', methods=['POST'])
def delete_flight(flight_id):
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # First check if there are any tickets for this flight
            cursor.execute("SELECT COUNT(*) FROM Ticket WHERE FlightID = %s", (flight_id,))
            ticket_count = cursor.fetchone()[0]
            
            if ticket_count > 0:
                flash('Cannot delete flight with existing tickets. Cancel the tickets first.')
                return redirect(url_for('admin_dashboard'))
            
            # Delete the flight
            cursor.execute("DELETE FROM Flight WHERE FlightID = %s", (flight_id,))
            connection.commit()
            flash('Flight deleted successfully!')
        except Error as e:
            connection.rollback()
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return redirect(url_for('admin_dashboard'))

# Route for searching flights
@app.route('/search', methods=['GET', 'POST'])
def search_flights():
    if request.method == 'POST':
        source = request.form.get('source', '').strip()
        destination = request.form.get('destination', '').strip()
        departure_date = request.form.get('departure_date', '').strip()
        trip_type = request.form.get('trip_type', 'one_way')
        return_date = request.form.get('return_date', '').strip()
        
        if not source or not destination or not departure_date:
            flash('Please fill in all required fields.')
            return render_template('search.html', search=False)
        
        connection = create_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                
                # Search for outbound flights
                query = """
                    SELECT f.*, a.Model, a.Capacity, 
                    COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                    FROM Flight f
                    LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                    WHERE f.Source LIKE %s AND f.Destination LIKE %s AND DATE(f.DepartureTime) = %s
                    ORDER BY f.DepartureTime
                """
                cursor.execute(query, (f"%{source}%", f"%{destination}%", departure_date))
                outbound_flights = cursor.fetchall()
                
                # If round trip, search for return flights
                return_flights = []
                if trip_type == 'round_trip' and return_date:
                    cursor.execute(query, (f"%{destination}%", f"%{source}%", return_date))
                    return_flights = cursor.fetchall()
                
                return render_template('search.html', 
                                    outbound_flights=outbound_flights,
                                    return_flights=return_flights,
                                    trip_type=trip_type,
                                    source=source,
                                    destination=destination,
                                    departure_date=departure_date,
                                    return_date=return_date,
                                    search=True,
                                    selected_outbound=None)
            except Error as e:
                flash(f"Error: {e}")
            finally:
                if connection.is_connected():
                    cursor.close()
                    connection.close()
    
    return render_template('search.html', search=False)

# Route for selecting return flight
@app.route('/select_return_flight', methods=['POST'])
def select_return_flight():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    outbound_flight_id = request.form.get('outbound_flight_id', '').strip()
    if not outbound_flight_id:
        flash('No outbound flight selected.')
        return redirect(url_for('search_flights'))

    try:
        outbound_flight_id = int(outbound_flight_id)
    except (ValueError, TypeError):
        flash('Invalid flight selection.')
        return redirect(url_for('search_flights'))

    source = request.form.get('source', '')
    destination = request.form.get('destination', '')
    departure_date = request.form.get('departure_date', '')
    return_date = request.form.get('return_date', '')
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)

            # Get outbound flight details
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity,
                COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                WHERE f.FlightID = %s
            """, (outbound_flight_id,))
            outbound_flight = cursor.fetchone()

            if not outbound_flight:
                flash('Outbound flight not found.')
                return redirect(url_for('search_flights'))

            # Find return flights
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity,
                COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                WHERE f.Source LIKE %s AND f.Destination LIKE %s AND DATE(f.DepartureTime) = %s
                ORDER BY f.DepartureTime
            """, (f"%{destination}%", f"%{source}%", return_date))
            return_flights = cursor.fetchall()

            return render_template('search.html',
                               outbound_flights=[outbound_flight],
                               return_flights=return_flights,
                               trip_type='round_trip',
                               source=source,
                               destination=destination,
                               departure_date=departure_date,
                               return_date=return_date,
                               selected_outbound=outbound_flight,
                               search=True)
        except Error as e:
            flash(f"Error: {e}")
            return redirect(url_for('search_flights'))
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    return redirect(url_for('search_flights'))

# Route for booking a flight
@app.route('/book/<int:flight_id>')
def book_flight(flight_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get flight details
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity, 
                COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                WHERE f.FlightID = %s
            """, (flight_id,))
            flight = cursor.fetchone()
            
            if not flight:
                flash('Flight not found.')
                return redirect(url_for('search_flights'))
            
            return render_template('booking.html', flight=flight, return_flight_id=None)
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return redirect(url_for('search_flights'))

# Route for processing flight booking
@app.route('/process_booking/<int:flight_id>', methods=['POST'])
def process_booking(flight_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get flight details
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity, 
                COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                WHERE f.FlightID = %s
            """, (flight_id,))
            flight = cursor.fetchone()
            
            if not flight:
                flash('Flight not found.')
                return redirect(url_for('search_flights'))
            
            user_id = session['user_id']
            travelers = []
            
            # Extract traveler information
            for key in request.form:
                if key.startswith('travelers[') and key.endswith('][first_name]'):
                    index = key[10:-13]
                    try:
                        traveler = {
                            'first_name': request.form.get(f'travelers[{index}][first_name]', '').strip(),
                            'last_name': request.form.get(f'travelers[{index}][last_name]', '').strip(),
                            'gender': request.form.get(f'travelers[{index}][gender]', '').strip(),
                            'age': request.form.get(f'travelers[{index}][age]', '').strip(),
                            'ff_airline': request.form.get(f'travelers[{index}][ff_airline]', '').strip(),
                            'ff_number': request.form.get(f'travelers[{index}][ff_number]', '').strip(),
                            'wheelchair': request.form.get(f'travelers[{index}][wheelchair]') == 'on'
                        }
                        if traveler['first_name'] and traveler['last_name'] and traveler['gender'] and traveler['age']:
                            travelers.append(traveler)
                    except Exception as e:
                        print(f"Error processing traveler {index}: {e}")
                        continue
            
            if not travelers:
                flash('Please provide at least one traveler with complete information.')
                return redirect(url_for('book_flight', flight_id=flight_id))
            
            # Check if enough seats are available
            available_seats = flight['Capacity'] - flight['BookedSeats']
            if len(travelers) > available_seats:
                flash(f'Only {available_seats} seats available, but you selected {len(travelers)} travelers.')
                return redirect(url_for('book_flight', flight_id=flight_id))
            
            base_price = 100.00 if flight['BookedSeats'] < flight['Capacity'] * 0.5 else 150.00
            
            try:
                for i, traveler in enumerate(travelers):
                    passenger_info = json.dumps({
                        'first_name': traveler['first_name'],
                        'last_name': traveler['last_name'],
                        'gender': traveler['gender'],
                        'age': int(traveler['age']),
                        'ff_airline': traveler['ff_airline'],
                        'ff_number': traveler['ff_number'],
                        'wheelchair': traveler['wheelchair']
                    })
                    
                    current_booked = flight['BookedSeats'] + i
                    seat_row = chr(65 + (current_booked // 6))
                    seat_col = (current_booked % 6) + 1
                    seat_number = f"{seat_row}{seat_col}"
                    
                    cursor.execute(
                        "INSERT INTO Ticket (PassengerID, FlightID, Price, SeatNumber, Status, PassengerInfo, TripType) VALUES (%s, %s, %s, %s, 'Booked', %s, 'One Way')",
                        (user_id, flight_id, base_price, seat_number, passenger_info)
                    )
                    ticket_id = cursor.lastrowid
                    
                    cursor.execute(
                        "INSERT INTO Payment (TicketID, Amount, Status) VALUES (%s, %s, 'Completed')",
                        (ticket_id, base_price)
                    )
                
                connection.commit()
                flash('Flight booked successfully!')
                return redirect(url_for('dashboard'))
            except Error as e:
                connection.rollback()
                flash(f"Booking failed: {e}")
                return redirect(url_for('book_flight', flight_id=flight_id))
                
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return redirect(url_for('search_flights'))

# Route for booking a round trip flight
@app.route('/book_round_trip/<int:outbound_flight_id>/<int:return_flight_id>')
def book_round_trip(outbound_flight_id, return_flight_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get outbound flight details
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity, 
                COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                WHERE f.FlightID = %s
            """, (outbound_flight_id,))
            outbound_flight = cursor.fetchone()
            
            # Get return flight details
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity, 
                COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                WHERE f.FlightID = %s
            """, (return_flight_id,))
            return_flight = cursor.fetchone()
            
            if not outbound_flight or not return_flight:
                flash('One or both flights not found.')
                return redirect(url_for('search_flights'))
            
            return render_template('booking.html', 
                                flight=outbound_flight,
                                return_flight=return_flight,
                                return_flight_id=return_flight_id)
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return redirect(url_for('search_flights'))

# Route for processing round trip booking
@app.route('/process_round_trip/<int:outbound_flight_id>/<int:return_flight_id>', methods=['POST'])
def process_round_trip(outbound_flight_id, return_flight_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get flight details
            cursor.execute("""
                SELECT f.*, a.Model, a.Capacity, 
                COALESCE((SELECT COUNT(*) FROM Ticket WHERE FlightID = f.FlightID AND Status = 'Booked'), 0) as BookedSeats
                FROM Flight f
                LEFT JOIN Aircraft a ON f.AircraftID = a.AircraftID
                WHERE f.FlightID IN (%s, %s)
            """, (outbound_flight_id, return_flight_id))
            flights = cursor.fetchall()
            
            if len(flights) != 2:
                flash('One or both flights not found.')
                return redirect(url_for('search_flights'))
            
            outbound_flight = next(f for f in flights if f['FlightID'] == outbound_flight_id)
            return_flight = next(f for f in flights if f['FlightID'] == return_flight_id)
            
            user_id = session['user_id']
            travelers = []
            
            # Extract traveler information
            for key in request.form:
                if key.startswith('travelers[') and key.endswith('][first_name]'):
                    index = key[10:-13]
                    try:
                        traveler = {
                            'first_name': request.form.get(f'travelers[{index}][first_name]', '').strip(),
                            'last_name': request.form.get(f'travelers[{index}][last_name]', '').strip(),
                            'gender': request.form.get(f'travelers[{index}][gender]', '').strip(),
                            'age': request.form.get(f'travelers[{index}][age]', '').strip(),
                            'ff_airline': request.form.get(f'travelers[{index}][ff_airline]', '').strip(),
                            'ff_number': request.form.get(f'travelers[{index}][ff_number]', '').strip(),
                            'wheelchair': request.form.get(f'travelers[{index}][wheelchair]') == 'on'
                        }
                        if traveler['first_name'] and traveler['last_name'] and traveler['gender'] and traveler['age']:
                            travelers.append(traveler)
                    except Exception as e:
                        print(f"Error processing traveler {index}: {e}")
                        continue
            
            if not travelers:
                flash('Please provide at least one traveler with complete information.')
                return redirect(url_for('book_round_trip', 
                                      outbound_flight_id=outbound_flight_id,
                                      return_flight_id=return_flight_id))
            
            # Check seat availability for both flights
            outbound_available = outbound_flight['Capacity'] - outbound_flight['BookedSeats']
            return_available = return_flight['Capacity'] - return_flight['BookedSeats']
            
            if len(travelers) > outbound_available:
                flash(f'Only {outbound_available} seats available on outbound flight.')
                return redirect(url_for('book_round_trip', 
                                      outbound_flight_id=outbound_flight_id,
                                      return_flight_id=return_flight_id))
            
            if len(travelers) > return_available:
                flash(f'Only {return_available} seats available on return flight.')
                return redirect(url_for('book_round_trip', 
                                      outbound_flight_id=outbound_flight_id,
                                      return_flight_id=return_flight_id))
            
            outbound_base_price = 100.00 if outbound_flight['BookedSeats'] < outbound_flight['Capacity'] * 0.5 else 150.00
            return_base_price = 100.00 if return_flight['BookedSeats'] < return_flight['Capacity'] * 0.5 else 150.00
            
            try:
                for i, traveler in enumerate(travelers):
                    passenger_info = json.dumps({
                        'first_name': traveler['first_name'],
                        'last_name': traveler['last_name'],
                        'gender': traveler['gender'],
                        'age': int(traveler['age']),
                        'ff_airline': traveler['ff_airline'],
                        'ff_number': traveler['ff_number'],
                        'wheelchair': traveler['wheelchair']
                    })
                    
                    # Outbound flight
                    current_booked = outbound_flight['BookedSeats'] + i
                    seat_row = chr(65 + (current_booked // 6))
                    seat_col = (current_booked % 6) + 1
                    seat_number = f"{seat_row}{seat_col}"
                    
                    cursor.execute(
                        "INSERT INTO Ticket (PassengerID, FlightID, Price, SeatNumber, Status, PassengerInfo, TripType) VALUES (%s, %s, %s, %s, 'Booked', %s, 'Round Trip')",
                        (user_id, outbound_flight_id, outbound_base_price, seat_number, passenger_info)
                    )
                    ticket_id = cursor.lastrowid
                    
                    cursor.execute(
                        "INSERT INTO Payment (TicketID, Amount, Status) VALUES (%s, %s, 'Completed')",
                        (ticket_id, outbound_base_price)
                    )
                    
                    # Return flight
                    current_booked = return_flight['BookedSeats'] + i
                    seat_row = chr(65 + (current_booked // 6))
                    seat_col = (current_booked % 6) + 1
                    seat_number = f"{seat_row}{seat_col}"
                    
                    cursor.execute(
                        "INSERT INTO Ticket (PassengerID, FlightID, Price, SeatNumber, Status, PassengerInfo, TripType) VALUES (%s, %s, %s, %s, 'Booked', %s, 'Round Trip')",
                        (user_id, return_flight_id, return_base_price, seat_number, passenger_info)
                    )
                    ticket_id = cursor.lastrowid
                    
                    cursor.execute(
                        "INSERT INTO Payment (TicketID, Amount, Status) VALUES (%s, %s, 'Completed')",
                        (ticket_id, return_base_price)
                    )
                
                connection.commit()
                flash('Round trip booked successfully!')
                return redirect(url_for('dashboard'))
            except Error as e:
                connection.rollback()
                flash(f"Booking failed: {e}")
                return redirect(url_for('book_round_trip', 
                                      outbound_flight_id=outbound_flight_id,
                                      return_flight_id=return_flight_id))
                
        except Error as e:
            flash(f"Error: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    return redirect(url_for('search_flights'))

# Route for terms and conditions
@app.route('/terms')
def terms_and_conditions():
    return render_template('terms.html')

# Run the application
if __name__ == '__main__':
    app.run(debug=True)