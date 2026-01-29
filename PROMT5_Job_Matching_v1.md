  # Prompt 5 — Job Matching + Explainability + Tailoring (v1)                                                                                                     
                                                                                                                                                                  
  Read SPEC.md and ARCHITECTURE.md.                                                                                                                               
                                                                                                                                                                  
  Implement Job Matching v1 end-to-end.                                                                                                                           
                                                                                                                                                                  
  ## Scope summary                                                                                                                                                
                                                                                                                                                                  
  Build:                                                                                                                                                          
                                                                                                                                                                  
  - Job ingestion (v1: 1–2 sources you can legally access)                                                                                                        
  - Matching pipeline                                                                                                                                             
  - Explainable matches UI                                                                                                                                        
  - Tailored resume + cover letter generation (DOCX)                                                                                                              
  - “Prepare” button per job row                                                                                                                                  
                                                                                                                                                                  
  Important constraints / realism:                                                                                                                                
                                                                                                                                                                  
  - You cannot scrape/automate LinkedIn or Google Jobs without their APIs/terms.                                                                                  
  - For v1, implement a provider adapter interface and wire up at least one legal source (e.g., The Muse, Remotive, Greenhouse public boards, Lever public        
    boards).                                                                                                                                                      
  - For “company career pages,” implement manual URL list ingestion (admin input) or a placeholder adapter with mocked data.                                      
  - Clearly document the limitations and where official API keys are required.                                                                                    
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ## Backend (services/api)                                                                                                                                       
                                                                                                                                                                  
  ### 1) Database models + migrations                                                                                                                             
                                                                                                                                                                  
  Add tables (Alembic migration required):                                                                                                                        
                                                                                                                                                                  
  jobs                                                                                                                                                            
                                                                                                                                                                  
  - id (PK)                                                                                                                                                       
  - source (string)
  - source_job_id (string)                                                                                                                                        
  - url (string)                                                                                                                                                  
  - title (string)                                                                                                                                                
  - company (string)                                                                                                                                              
  - location (string)                                                                                                                                             
  - remote_flag (bool)                                                                                                                                            
  - salary_min (int nullable)                                                                                                                                     
  - salary_max (int nullable)                                                                                                                                     
  - currency (string nullable)                                                                                                                                    
  - description_text (text)                                                                                                                                       
  - content_hash (string, indexed)                                                                                                                                
  - posted_at (timestamp nullable)                                                                                                                                
  - ingested_at (timestamp)                                                                                                                                       
  - application_deadline (timestamp nullable)                                                                                                                     
  - hiring_manager_name (string nullable)                                                                                                                         
  - hiring_manager_email (string nullable)                                                                                                                        
  - hiring_manager_phone (string nullable)                                                                                                                        
                                                                                                                                                                  
  matches                                                                                                                                                         
                                                                                                                                                                  
  - id (PK)                                                                                                                                                       
  - user_id (FK users.id)                                                                                                                                         
  - job_id (FK jobs.id)                                                                                                                                           
  - profile_version (int)                                                                                                                                         
  - match_score (0–100)                                                                                                                                           
  - interview_readiness_score (0–100)                                                                                                                             
  - offer_probability (0–100)                                                                                                                                     
  - reasons (jsonb)                                                                                                                                               
  - created_at                                                                                                                                                    
                                                                                                                                                                  
  tailored_resumes                                                                                                                                                
                                                                                                                                                                  
  - id (PK)                                                                                                                                                       
  - user_id (FK)                                                                                                                                                  
  - job_id (FK)                                                                                                                                                   
  - profile_version (int)                                                                                                                                         
  - docx_url (string)                                                                                                                                             
  - cover_letter_url (string)                                                                                                                                     
  - change_log (jsonb)                                                                                                                                            
  - created_at                                                                                                                                                    
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ### 2) Job ingestion (v1)                                                                                                                                       
                                                                                                                                                                  
  Implement an adapter interface:                                                                                                                                 
                                                                                                                                                                  
  class JobSource:                                                                                                                                                
    def fetch_jobs(self, query: dict) -> list[JobPosting]                                                                                                         
                                                                                                                                                                  
  Provide at least one working adapter using a legal API or public job feed.                                                                                      
                                                                                                                                                                  
  - Example: Remotive API or The Muse API                                                                                                                         
  - Deduplicate via content_hash (hash of title+company+location+description)                                                                                     
  - Store jobs in DB                                                                                                                                              
                                                                                                                                                                  
  Add a background job:                                                                                                                                           
                                                                                                                                                                  
  - ingest_jobs(query) (RQ)                                                                                                                                       
  - writes to jobs table                                                                                                                                          
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ### 3) Matching pipeline                                                                                                                                        
                                                                                                                                                                  
  Create a matching worker:                                                                                                                                       
                                                                                                                                                                  
  - Inputs: user_id, profile_version                                                                                                                              
  - Uses candidate profile + preferences                                                                                                                          
  - Scores top jobs with deterministic heuristics:                                                                                                                
                                                                                                                                                                  
  Match Score (0–100)                                                                                                                                             
                                                                                                                                                                  
  - skill overlap (weighted)                                                                                                                                      
  - title similarity                                                                                                                                              
  - location + remote preference                                                                                                                                  
  - salary fit                                                                                                                                                    
  - years_experience fit                                                                                                                                          
                                                                                                                                                                  
  Interview Readiness Score (0–100)                                                                                                                               
                                                                                                                                                                  
  - match_score                                                                                                                                                   
  - evidence strength (presence of quantified bullets)                                                                                                            
  - gaps severity                                                                                                                                                 
                                                                                                                                                                  
  Offer Probability (0–100)                                                                                                                                       
                                                                                                                                                                  
  - simple heuristic (not guaranteed)                                                                                                                             
  - derived from match_score + readiness + years_experience fit                                                                                                   
                                                                                                                                                                  
  Store reasons JSON with top 3–7 items:                                                                                                                          
                                                                                                                                                                  
  - matched_skills                                                                                                                                                
  - missing_skills                                                                                                                                                
  - title_alignment                                                                                                                                               
  - location_fit                                                                                                                                                  
  - salary_fit                                                                                                                                                    
  - evidence_refs                                                                                                                                                 
                                                                                                                                                                  
  Important: This is explainable, not ML.                                                                                                                         
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ### 4) Matching endpoints                                                                                                                                       
                                                                                                                                                                  
  - POST /api/matches/refresh                                                                                                                                     
      - enqueue matching job                                                                                                                                      
  - GET /api/matches                                                                                                                                              
      - returns top 5 by score for current user                                                                                                                   
  - GET /api/matches/{match_id}                                                                                                                                   
      - returns job detail + reasons                                                                                                                              
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ### 5) Tailored resume + cover letter generation                                                                                                                
                                                                                                                                                                  
  Add endpoint:                                                                                                                                                   
                                                                                                                                                                  
  - POST /api/tailor/{job_id}                                                                                                                                     
                                                                                                                                                                  
  Behavior:                                                                                                                                                       
                                                                                                                                                                  
  - Enqueue worker job                                                                                                                                            
  - Worker generates:                                                                                                                                             
      1. ATS resume DOCX                                                                                                                                          
      2. Cover letter DOCX                                                                                                                                        
                                                                                                                                                                  
  Output stored in local dev folder and returns URLs (local dev placeholder).                                                                                     
                                                                                                                                                                  
  #### Resume formatting rules                                                                                                                                    
                                                                                                                                                                  
  - Single column                                                                                                                                                 
  - Calibri 11 body, Calibri 12 bold headings                                                                                                                     
  - Standard headings: Work Experience, Education, Certifications, Skills                                                                                         
  - Title at top must match target job title exactly                                                                                                              
  - Mirror terminology from job description                                                                                                                       
  - Use action-verb + quantified result where possible                                                                                                            
  - No fabrication: only from resume/profile                                                                                                                      
                                                                                                                                                                  
  #### Cover letter rules                                                                                                                                         
                                                                                                                                                                  
  - Under 1 page, 3–4 short paragraphs or bullets                                                                                                                 
  - Highly tailored to top 3 job requirements                                                                                                                     
  - Demonstrate company research (if not available, include neutral placeholder)                                                                                  
  - Address hiring manager by name if available                                                                                                                   
  - End with confident, professional closing asking for interview                                                                                                 
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ### 6) Authentication + gating                                                                                                                                  
                                                                                                                                                                  
  - Require auth for all new endpoints.                                                                                                                           
  - Use require_onboarded_user and require_allowed_trust where applicable.                                                                                        
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ## Frontend (apps/web)                                                                                                                                          
                                                                                                                                                                  
  ### 1) Matches dashboard                                                                                                                                        
                                                                                                                                                                  
  - New /matches page                                                                                                                                             
  - Fetch top 5 matches                                                                                                                                           
  - Show table with:                                                                                                                                              
      - Company Name                                                                                                                                              
      - Link to job posting                                                                                                                                       
      - Job Title                                                                                                                                                 
      - Job Description (truncated + expandable)                                                                                                                  
      - Location                                                                                                                                                  
      - Application Deadline                                                                                                                                      
      - Hiring Manager Name                                                                                                                                       
      - Hiring Manager Email                                                                                                                                      
      - Hiring Manager Phone                                                                                                                                      
      - Button “Prepare”                                                                                                                                          
                                                                                                                                                                  
  ### 2) Prepare button                                                                                                                                           
                                                                                                                                                                  
  - Calls POST /api/tailor/{job_id}                                                                                                                               
  - Shows progress status (poll status endpoint if needed)                                                                                                        
  - When ready, show download links for:                                                                                                                          
      - Tailored resume DOCX                                                                                                                                      
      - Cover letter DOCX                                                                                                                                         
                                                                                                                                                                  
  ———                                                                                                                                                             
                                                                                                                                                                  
  ## Important UX notes                                                                                                                                           
                                                                                                                                                                  
  - No manual job link input.                                                                                                                                     

  ———

  ## Deliverables

  - Migrations
  - New APIs
  - New worker jobs
  - Matches UI
  - Tailoring generation
  - README updates

  Return code changes only.