import sqlite3
import csv
import io
import re
from datetime import datetime

DB_PATH = 'backend/bloodbank.db'

RAW_CSV = """Donor ID,Name,DOB,Gender,Blood Group,Last Donated,Fake Mobile Number,District,Taluk,Fictional Address,Latitude,Longitude,Availability,Consent
KD00001,Arjun Patil,1992-06-08,Male,B+,2025-06-18,TEST-PHONE-0001,Kalaburagi,Chincholi,"Fictional locality, Chincholi, Kalaburagi, Karnataka",17.47,77.42,Unverified,Synthetic
KD00002,Meghana Kulkarni,1976-03-25,Female,AB-,2024-12-16,TEST-PHONE-0002,Gadag,Mundargi,"Fictional locality, Mundargi, Gadag, Karnataka",15.21,75.88,Unverified,Synthetic
KD00003,Dhanush Mallya,1973-08-23,Male,A+,2026-06-10,TEST-PHONE-0003,Uttara Kannada,Siddapur,"Fictional locality, Siddapur, Uttara Kannada, Karnataka",14.34,74.89,Unverified,Synthetic
KD00004,Roopa Vaidya,1972-04-10,Female,AB-,2026-09-05,TEST-PHONE-0004,Tumakuru,Pavagada,"Fictional locality, Pavagada, Tumakuru, Karnataka",14.1,77.28,Unverified,Synthetic
KD00005,Niranjan Ravindra,1985-01-12,Male,AB-,2025-12-20,TEST-PHONE-0005,Yadgir,Hunsagi,"Fictional locality, Hunsagi, Yadgir, Karnataka",16.67,76.64,Unverified,Synthetic
KD00006,Siddharth Srinath,1987-10-26,Male,A-,2026-08-25,TEST-PHONE-0006,Vijayapura,Talikoti,"Fictional locality, Talikoti, Vijayapura, Karnataka",16.47,76.31,Unverified,Synthetic
KD00007,Ishwar Prabhu,1990-04-26,Male,A+,2025-09-21,TEST-PHONE-0007,Vijayapura,Chadchan,"Fictional locality, Chadchan, Vijayapura, Karnataka",17.28,76.35,Unverified,Synthetic
KD00008,Sanjith Shenoy,1990-03-09,Male,AB+,2026-06-22,TEST-PHONE-0008,Mandya,Krishnarajpet,"Fictional locality, Krishnarajpet, Mandya, Karnataka",12.67,76.49,Unverified,Synthetic
KD00009,Sanjukta Joshi,1993-11-15,Female,O-,2024-11-22,TEST-PHONE-0009,Bagalkote,Hungund,"Fictional locality, Hungund, Bagalkote, Karnataka",16.06,76.06,Unverified,Synthetic
KD00010,Hemanth Vaidya,1973-10-15,Male,O-,2026-03-10,TEST-PHONE-0010,Tumakuru,Tumakuru,"Fictional locality, Tumakuru, Tumakuru, Karnataka",13.34,77.1,Unverified,Synthetic
KD00011,Jahnavi Patil,1979-05-15,Female,O+,2025-03-02,TEST-PHONE-0011,Bidar,Bhalki,"Fictional locality, Bhalki, Bidar, Karnataka",18.04,77.21,Unverified,Synthetic
KD00012,Jayashree Kamath,1988-12-28,Female,AB+,2025-05-24,TEST-PHONE-0012,Udupi,Kapu,"Fictional locality, Kapu, Udupi, Karnataka",13.22,74.74,Unverified,Synthetic
KD00013,Sudarshan Subramanya,1979-03-14,Male,A+,2026-01-26,TEST-PHONE-0013,Vijayapura,Tikota,"Fictional locality, Tikota, Vijayapura, Karnataka",16.82,75.52,Unverified,Synthetic
KD00014,Aarav Naik,1986-10-11,Male,A+,2026-08-18,TEST-PHONE-0014,Chikkaballapura,Sidlaghatta,"Fictional locality, Sidlaghatta, Chikkaballapura, Karnataka",13.39,77.86,Unverified,Synthetic
KD00015,Sanjay Shenoy,1985-11-03,Male,O+,2026-01-30,TEST-PHONE-0015,Koppal,Karatagi,"Fictional locality, Karatagi, Koppal, Karnataka",15.62,76.53,Unverified,Synthetic
KD00016,Praveen Rao,1976-10-25,Male,O+,2025-07-06,TEST-PHONE-0016,Bidar,Aurad,"Fictional locality, Aurad, Bidar, Karnataka",18.25,77.42,Unverified,Synthetic
KD00017,Jahnavi Nayakar,1970-09-15,Female,A+,2025-08-23,TEST-PHONE-0017,Raichur,Lingasugur,"Fictional locality, Lingasugur, Raichur, Karnataka",16.16,76.52,Unverified,Synthetic
KD00018,Nisha Reddy,1981-08-11,Female,AB+,2025-01-02,TEST-PHONE-0018,Chikkaballapura,Chelur,"Fictional locality, Chelur, Chikkaballapura, Karnataka",13.44,77.73,Unverified,Synthetic
KD00019,Rishab Kashyap,1977-11-25,Male,O+,2025-02-24,TEST-PHONE-0019,Kolar,Kolar,"Fictional locality, Kolar, Kolar, Karnataka",13.14,78.13,Unverified,Synthetic
KD00020,Vikas Reddy,1990-03-12,Male,A+,2026-02-16,TEST-PHONE-0020,Yadgir,Gurmitkal,"Fictional locality, Gurmitkal, Yadgir, Karnataka",16.87,77.39,Unverified,Synthetic
KD00021,Chaitra Adiga,2002-10-17,Female,AB+,2025-10-16,TEST-PHONE-0021,Bagalkote,Ilkal,"Fictional locality, Ilkal, Bagalkote, Karnataka",15.96,76.11,Unverified,Synthetic
KD00022,Ankita Nayakar,1992-09-28,Female,A-,2025-09-16,TEST-PHONE-0022,Belagavi,Khanapur,"Fictional locality, Khanapur, Belagavi, Karnataka",15.64,74.51,Unverified,Synthetic
KD00023,Aditya Gowda,1985-01-14,Male,O+,2026-06-25,TEST-PHONE-0023,Chikkamagaluru,Narasimharajapura,"Fictional locality, Narasimharajapura, Chikkamagaluru, Karnataka",13.61,75.51,Unverified,Synthetic
KD00024,Mohan Hegde,1995-02-14,Male,O-,2025-12-31,TEST-PHONE-0024,Bengaluru Rural,Hoskote,"Fictional locality, Hoskote, Bengaluru Rural, Karnataka",13.07,77.8,Unverified,Synthetic
KD00025,Keerthana Mallya,1985-02-11,Female,A+,2025-03-08,TEST-PHONE-0025,Belagavi,Yaragatti,"Fictional locality, Yaragatti, Belagavi, Karnataka",15.85,74.5,Unverified,Synthetic
KD00026,Venkatesh Subramanya,1974-12-07,Male,B-,2026-05-08,TEST-PHONE-0026,Hassan,Holenarasipura,"Fictional locality, Holenarasipura, Hassan, Karnataka",12.78,76.24,Unverified,Synthetic
KD00027,Rashmi Swamy,2000-06-06,Female,B-,2025-09-15,TEST-PHONE-0027,Koppal,Kanakagiri,"Fictional locality, Kanakagiri, Koppal, Karnataka",15.57,76.52,Unverified,Synthetic
KD00028,Madhuri Bhandary,1972-01-10,Female,O+,2026-09-05,TEST-PHONE-0028,Vijayanagara,Hoovina Hadagali,"Fictional locality, Hoovina Hadagali, Vijayanagara, Karnataka",15.02,75.93,Unverified,Synthetic
KD00029,Pallavi Kashyap,1996-01-10,Female,A-,2025-04-29,TEST-PHONE-0029,Kalaburagi,Aland,"Fictional locality, Aland, Kalaburagi, Karnataka",17.57,76.57,Unverified,Synthetic
KD00030,Vasudha Subramanya,1975-06-09,Female,AB+,2026-04-19,TEST-PHONE-0030,Mysuru,Saligrama,"Fictional locality, Saligrama, Mysuru, Karnataka",12.3,76.64,Unverified,Synthetic
KD00031,Pranav Naik,1988-01-02,Male,AB+,2026-03-18,TEST-PHONE-0031,Vijayanagara,Hosapete,"Fictional locality, Hosapete, Vijayanagara, Karnataka",15.27,76.39,Unverified,Synthetic
KD00032,Yashas Acharya,1983-08-17,Male,O-,2026-07-31,TEST-PHONE-0032,Tumakuru,Gubbi,"Fictional locality, Gubbi, Tumakuru, Karnataka",13.31,76.94,Unverified,Synthetic
KD00033,Mohan Swamy,1997-05-15,Male,A-,2026-06-06,TEST-PHONE-0033,Udupi,Kapu,"Fictional locality, Kapu, Udupi, Karnataka",13.22,74.74,Unverified,Synthetic
KD00034,Manjunath Reddy,1982-04-27,Male,B-,2025-04-19,TEST-PHONE-0034,Haveri,Savanur,"Fictional locality, Savanur, Haveri, Karnataka",14.97,75.34,Unverified,Synthetic
KD00035,Raksha Kamath,1976-04-24,Female,O+,2026-07-15,TEST-PHONE-0035,Shivamogga,Soraba,"Fictional locality, Soraba, Shivamogga, Karnataka",14.38,75.1,Unverified,Synthetic
KD00036,Dhanush Kulkarni,1986-10-21,Male,B-,2026-07-25,TEST-PHONE-0036,Vijayapura,Basavana Bagewadi,"Fictional locality, Basavana Bagewadi, Vijayapura, Karnataka",16.57,76,Unverified,Synthetic
KD00037,Divya Gowdar,1981-02-10,Female,B-,2026-03-19,TEST-PHONE-0037,Kalaburagi,Aland,"Fictional locality, Aland, Kalaburagi, Karnataka",17.57,76.57,Unverified,Synthetic
KD00038,Aarav Jain,1992-02-17,Male,O-,2025-01-11,TEST-PHONE-0038,Mysuru,Saragur,"Fictional locality, Saragur, Mysuru, Karnataka",12.3,76.64,Unverified,Synthetic
KD00039,Madhav Urs,1996-10-06,Male,B+,2026-03-13,TEST-PHONE-0039,Dharwad,Kalghatgi,"Fictional locality, Kalghatgi, Dharwad, Karnataka",15.18,74.97,Unverified,Synthetic
KD00040,Mahesh Pai,1996-10-17,Male,AB-,2026-07-09,TEST-PHONE-0040,Haveri,Hirekerur,"Fictional locality, Hirekerur, Haveri, Karnataka",14.46,75.4,Unverified,Synthetic
KD00041,Girish Kulkarni,1974-01-22,Male,B+,2025-07-15,TEST-PHONE-0041,Chikkaballapura,Gudibanda,"Fictional locality, Gudibanda, Chikkaballapura, Karnataka",13.44,77.73,Unverified,Synthetic
KD00042,Ramesh Kamat,2004-02-02,Male,AB-,2025-07-05,TEST-PHONE-0042,Mandya,Maddur,"Fictional locality, Maddur, Mandya, Karnataka",12.58,77.04,Unverified,Synthetic
KD00043,Akshay Reddy,1982-04-08,Male,AB+,2025-04-14,TEST-PHONE-0043,Shivamogga,Thirthahalli,"Fictional locality, Thirthahalli, Shivamogga, Karnataka",13.69,75.24,Unverified,Synthetic
KD00044,Kavya Mallya,1971-07-27,Female,B+,2024-12-29,TEST-PHONE-0044,Dharwad,Hubballi Urban,"Fictional locality, Hubballi Urban, Dharwad, Karnataka",15.36,75.14,Unverified,Synthetic
KD00045,Rohit Joshi,1984-11-11,Male,AB-,2025-03-19,TEST-PHONE-0045,Chikkaballapura,Gudibanda,"Fictional locality, Gudibanda, Chikkaballapura, Karnataka",13.44,77.73,Unverified,Synthetic
KD00046,Chethan Gowdar,2003-11-16,Male,B-,2025-09-21,TEST-PHONE-0046,Koppal,Gangavathi,"Fictional locality, Gangavathi, Koppal, Karnataka",15.43,76.53,Unverified,Synthetic
KD00047,Anirudh Bhandary,2003-09-24,Male,O+,2026-07-11,TEST-PHONE-0047,Kalaburagi,Afzalpur,"Fictional locality, Afzalpur, Kalaburagi, Karnataka",17.2,76.36,Unverified,Synthetic
KD00048,Naveen Shenoy,2004-02-05,Male,A-,2026-04-28,TEST-PHONE-0048,Bidar,Chitgoppa,"Fictional locality, Chitgoppa, Bidar, Karnataka",17.91,77.52,Unverified,Synthetic
KD00049,Sanjukta Hebbar,1979-09-05,Female,AB+,2025-07-31,TEST-PHONE-0049,Uttara Kannada,Dandeli,"Fictional locality, Dandeli, Uttara Kannada, Karnataka",15.25,74.62,Unverified,Synthetic
KD00050,Roopa Rao,2000-07-24,Female,AB+,2026-01-07,TEST-PHONE-0050,Kolar,Malur,"Fictional locality, Malur, Kolar, Karnataka",13,77.94,Unverified,Synthetic
"""

def test():
    f = io.StringIO(RAW_CSV)
    reader = csv.DictReader(f)
    rows = list(reader)
    print(f"Loaded {len(rows)} test records from snippet.")
    print("Sample record:", rows[0])

if __name__ == '__main__':
    test()
