# Viva Examination Questions and Answers (25 Key Technical Questions)

**Project Title**: Online Blood Bank Management System with Donor Availability Prediction using Machine Learning  
**Target Audience**: B.E. / B.Tech Major Project Oral Defense & External Examiner Evaluation  

---

## SECTION 1: MACHINE LEARNING & DATA SCIENCE

### Q1: Why did you choose Random Forest Classifier over Logistic Regression and Decision Trees for your final model?
**Answer**: Random Forest achieved superior overall performance with an **Accuracy of 90.42%** and an **F1 Score of 93.80%**, compared to Decision Tree (91.88% F1) and Logistic Regression (88.52% F1). More importantly, Random Forest demonstrated a **Recall of 98.31%**. In a medical emergency application, Recall is the most critical metric because False Negatives (predicting an available donor as unavailable) mean missing out on potential life-saving donors. Random Forest's ensemble bagging approach also prevents overfitting compared to a single Decision Tree.

### Q2: What features were used in your ML dataset, and how were they preprocessed?
**Answer**: We used 11 predictor features:
- **Numerical**: `age`, `distance_km`, `last_donation_days`, `donation_frequency`, `previous_response_rate`, `response_time_hrs`, `health_eligibility_score`.
- **Categorical**: `gender`, `blood_group`, `location`, `preferred_time`.

Preprocessing was built into a Scikit-Learn `ColumnTransformer` pipeline:
- Numerical features were standardized using `StandardScaler` ($z = \frac{x - \mu}{\sigma}$).
- Categorical features were encoded using `OneHotEncoder(handle_unknown='ignore')`.

### Q3: What is the significance of the F1 Score, and why isn't Accuracy alone sufficient?
**Answer**: Accuracy simply measures the proportion of total correct predictions. In datasets where class imbalance exists (e.g., more donors are available than unavailable), a model predicting only the majority class could show high accuracy while failing to identify unavailable donors. F1 Score is the harmonic mean of Precision and Recall:

$$F1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

It provides a balanced measure of both False Positives and False Negatives.

### Q4: How is the Donor Availability Score (0-100) calculated?
**Answer**: The raw prediction probability $P(Y=1 | X)$ is extracted from `pipeline.predict_proba(X)[:, 1]`. This continuous probability (ranging between 0.0 and 1.0) is multiplied by 100 to yield a standardized **Donor Availability Score (0–100)**. Donors are categorized as:
- **High Availability**: Score $\ge 75$
- **Medium Availability**: $40 \le \text{Score} < 75$
- **Low Availability**: Score $< 40$

### Q5: How do you handle new or unseen categorical values during real-time model inference?
**Answer**: In our Scikit-Learn pipeline, `OneHotEncoder` is configured with `handle_unknown='ignore'`. When an unknown categorical value is passed during prediction, all encoded one-hot columns for that feature are set to zero, preventing runtime exceptions.

---

## SECTION 2: SYSTEM ARCHITECTURE & BACKEND DEVELOPMENT

### Q6: Explain the architectural pattern used in your project.
**Answer**: We implemented a decoupled **4-Tier Microservice Architecture**:
1. **Presentation Tier**: React.js SPA + Tailwind CSS UI.
2. **Business Tier**: Java 17 Spring Boot REST API for security, user roles, inventory, and request management.
3. **Data Tier**: MySQL Relational Database (3NF) storing domain entities.
4. **Machine Learning Microservice**: Python FastAPI server executing Scikit-Learn pipeline inference.

### Q7: How does Spring Boot secure REST endpoints?
**Answer**: Spring Boot uses **Spring Security** combined with **JSON Web Tokens (JWT)**. When a user logs in via `/api/v1/auth/login`, the server validates credentials and generates a signed JWT token containing user ID, email, and role claims. Subsequent HTTP requests include the header `Authorization: Bearer <token>`. A custom `JwtAuthenticationFilter` intercepts requests, validates the signature using HMAC-SHA256, and populates the `SecurityContextHolder`.

### Q8: What database normalization level is implemented, and why?
**Answer**: The database schema is normalized up to **Third Normal Form (3NF)** to eliminate data redundancy and prevent insertion, update, and deletion anomalies. Every non-prime attribute is non-transitively dependent on the primary key.

### Q9: Why is Spring Data JPA preferred over traditional JDBC?
**Answer**: Spring Data JPA abstracts database operations by mapping Java objects directly to relational tables via Hibernate ORM. It provides repository interfaces (`JpaRepository`) with built-in CRUD operations and custom query derivation (`findByBloodGroup`), reducing boilerplate SQL code and improving code maintainability.

### Q10: How does the Spring Boot backend communicate with the Python ML Service?
**Answer**: Communication occurs over HTTP REST calls. When an emergency request requires ML predictions, Spring Boot's `RestTemplate` or `WebClient` sends a POST request with donor feature JSON payload to `http://localhost:8000/predict`. The FastAPI service executes inference and returns the JSON score response.

---

## SECTION 3: FRONTEND & USER INTERFACE

### Q11: Why did you choose React.js over traditional HTML/JSP pages?
**Answer**: React.js enables a component-driven Single Page Application (SPA) architecture. Component state re-renders only the changed DOM nodes via the Virtual DOM, delivering instantaneous UI responsiveness without full-page reloads.

### Q12: How is role-based dashboard navigation handled on the frontend?
**Answer**: Navigation and access control are managed using React state and contextual guards (`activeRole`). Components verify whether the authenticated user possesses the appropriate role (`ROLE_ADMIN`, `ROLE_DONOR`, `ROLE_HOSPITAL`, `ROLE_STAFF`) before rendering authorized navigation panels.

### Q13: What is Tailwind CSS, and what advantages does it offer over custom CSS?
**Answer**: Tailwind CSS is a utility-first CSS framework. Rather than writing custom class definitions, layout, typography, colors, and responsive states are applied directly using predefined utility classes. This eliminates CSS file bloat and speeds up development.

---

## SECTION 4: TESTING, DEPLOYMENT & DATABASE

### Q14: How are database indexes used in your MySQL schema?
**Answer**: Indexes were created on high-frequency query columns:
```sql
CREATE INDEX idx_donors_bg ON donors(blood_group);
CREATE INDEX idx_donors_location ON donors(location);
CREATE INDEX idx_requests_status ON blood_requests(status);
```
Indexes use B-Tree data structures to reduce search time complexity from $O(N)$ table scans to $O(\log N)$ index lookups during emergency donor searches.

### Q15: How did you handle CORS (Cross-Origin Resource Sharing) between React (Port 3000) and Backend APIs (Port 8080/8000)?
**Answer**: CORS rules were configured using `@CrossOrigin(origins = "*")` in Spring Boot controllers and `CORSMiddleware` in FastAPI to allow HTTP methods (GET, POST, PUT, DELETE) from the React origin.

---

## SECTION 5: VIVA REVISION QUICK RECAP (Q16 - Q25)

* **Q16**: What is overfitting in Decision Trees, and how does Random Forest resolve it?  
  *Answer*: Decision trees tend to grow deep and memorize noise in training data. Random Forest constructs an ensemble of multiple de-correlated trees using random feature subsets and averages their votes, reducing variance.
* **Q17**: What is JWT structure?  
  *Answer*: Header.Payload.Signature (3 base64url-encoded parts).
* **Q18**: What is the purpose of `schema.sql` and `data.sql`?  
  *Answer*: `schema.sql` creates tables and indices; `data.sql` populates initial test seed records upon startup.
* **Q19**: How do you calculate distance in the dataset?  
  *Answer*: Using Haversine formula or Euclidean distance metrics derived from latitude/longitude coordinates.
* **Q20**: How is donor privacy protected?  
  *Answer*: Sensitive credentials are encrypted using BCrypt hash algorithms; contact numbers are accessible only to verified staff and hospitals during emergency dispatches.
* **Q21**: What happens if the Python ML service is offline?  
  *Answer*: Spring Boot falls back to a deterministic rule-based calculation based on `last_donation_days` and `previous_response_rate`, ensuring high system availability.
* **Q22**: What is a Confusion Matrix?  
  *Answer*: A $2 \times 2$ table showing True Positives, True Negatives, False Positives, and False Negatives.
* **Q23**: How does the system handle blood component expiration?  
  *Answer*: Automated database status triggers flag inventory components as `EXPIRED` once `expiry_date < CURRENT_DATE`.
* **Q24**: What is standard blood shelf life?  
  *Answer*: Whole Blood/Red Cells: 35–42 days; Platelets: 5 days; Plasma: 1 year (frozen).
* **Q25**: What is the main societal contribution of your major project?  
  *Answer*: Automating blood bank operations and applying predictive ML to rank donor availability reduces emergency dispatch latency, saving critical human lives during trauma medical shortages.
