

/*1. Employee Table */
 
CREATE TABLE dbo.Employee (
    EmployeeID INT IDENTITY(1,1) PRIMARY KEY,
    EmployeeCode VARCHAR(20),
    FirstName VARCHAR(50),
    LastName VARCHAR(50),
    Email VARCHAR(100),
    Phone VARCHAR(20),
    DepartmentID INT,
    JobTitle VARCHAR(100),
    ManagerID INT NULL,
    HireDate DATE,
    Salary DECIMAL(12,2),
    City VARCHAR(50),
    Status VARCHAR(20)
);


/*2. Insert Sample data into Employee Table */
 
INSERT INTO dbo.Employee
(EmployeeCode, FirstName, LastName, Email, Phone, DepartmentID, JobTitle, ManagerID, HireDate, Salary, City, Status)
VALUES
('EMP001','Sandeep','Kumar','sandeep@contoso.com','9876543210',1,'HR Manager',NULL,'2021-01-10',120000,'Bangalore','Active'),
('EMP002','Anita','Sharma','anita@contoso.com','9876543211',2,'Software Engineer',4,'2022-03-15',85000,'Hyderabad','Active'),
('EMP003','Rahul','Verma','rahul@contoso.com','9876543212',2,'Senior Developer',4,'2020-06-20',110000,'Pune','Active'),
('EMP004','Priya','Reddy','priya@contoso.com','9876543213',2,'Engineering Manager',NULL,'2019-02-01',150000,'Bangalore','Active'),
('EMP005','Arjun','Patel','arjun@contoso.com','9876543214',3,'Finance Analyst',6,'2023-01-18',70000,'Mumbai','Active'),
('EMP006','Neha','Gupta','neha@contoso.com','9876543215',3,'Finance Manager',NULL,'2018-07-11',135000,'Delhi','Active'),
('EMP007','Kiran','Das','kiran@contoso.com','9876543216',4,'Sales Executive',8,'2022-05-12',65000,'Chennai','Active'),
('EMP008','Meera','Nair','meera@contoso.com','9876543217',4,'Sales Manager',NULL,'2019-08-08',140000,'Bangalore','Active');
