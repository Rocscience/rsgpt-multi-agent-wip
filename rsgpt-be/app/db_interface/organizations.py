from app.db_models.organizations import (
    OrganizationsORM,
    UserOrganizationsORM
)
from app.models.organizations import (
    CreateOrganizationRequest,
    CreateOrganizationResponse
)
from app.db_models.connection import Session
from uuid import UUID
from datetime import date
from typing import List


def create_organization(org_request: CreateOrganizationRequest) -> OrganizationsORM:
    """Create a new organization"""
    try:
        with Session() as session:
            new_org = OrganizationsORM(
                id=org_request.id,
                name=org_request.name,
                question_quota=org_request.question_quota,
                access_level=org_request.access_level,
                quota_reset_date=org_request.quota_reset_date,
                rocportal_status=org_request.rocportal_status
            )
            session.add(new_org)
            session.commit()
            session.refresh(new_org)
            session.expunge(new_org)
            return new_org
    except Exception as e:
        raise e

def get_organization_by_id(organization_id: str) -> OrganizationsORM:
    """Get an organization by id"""
    try:
        with Session() as session:
            org = session.query(OrganizationsORM).filter(OrganizationsORM.id == organization_id).first()
            if org:
                session.expunge(org)
            return org
    except Exception as e:
        raise e

def get_organization_by_user_id(user_id: str) -> OrganizationsORM:
    """Get an organization by user_id"""
    try:
        with Session() as session:
            # Get the user's OrganizationORM by checking the user_organizations table
            user_org = session.query(UserOrganizationsORM).filter(UserOrganizationsORM.user_id == user_id).first()
            if user_org:
                org = user_org.organizations_orm
                session.expunge(org)
                return org
            else:
                return None 
    except Exception as e:
        raise e
    
def reassign_user_organization(user_id: str, new_organization_id: str) -> UserOrganizationsORM:
    """Reassign a user to a different organization by updating their user_organizations row.

    This handles the case where a user was previously assigned to a self-created BASIC org
    but rocportal indicates they belong to a licensed FLEXIBLE org. The existing row is
    updated to point to the correct org rather than inserting a duplicate.
    """
    try:
        with Session() as session:
            user_org = session.query(UserOrganizationsORM).filter(
                UserOrganizationsORM.user_id == user_id
            ).first()
            if user_org:
                user_org.organization_id = new_organization_id
                session.commit()
                session.refresh(user_org)
                session.expunge(user_org)
                return user_org
            else:
                # No existing row — create a new one
                new_user_org = UserOrganizationsORM(user_id=user_id, organization_id=new_organization_id)
                session.add(new_user_org)
                session.commit()
                session.refresh(new_user_org)
                session.expunge(new_user_org)
                return new_user_org
    except Exception as e:
        raise e

def add_user_to_organization(user_id: str, organization_id: str) -> UserOrganizationsORM:
    """Add a user to an organization"""
    try:
        with Session() as session:
            user_org = UserOrganizationsORM(user_id=user_id, organization_id=organization_id)
            session.add(user_org)
            session.commit()
            session.refresh(user_org)
            session.expunge(user_org)
            return user_org
    except Exception as e:
        raise e
    
def update_organization_quota(organization_id: str, question_quota: int, rocportal_status: bool, access_level: str = None) -> OrganizationsORM:
    """Update an organization's quota, rocportal_status, and access_level from rocportal data"""
    try:
        with Session() as session:
            organization = session.query(OrganizationsORM).filter(OrganizationsORM.id == organization_id).first()
            organization.question_quota = question_quota
            organization.rocportal_status = rocportal_status
            if access_level is not None:
                organization.access_level = access_level
            session.commit()
            session.refresh(organization)
            session.expunge(organization)
            return organization
    except Exception as e:
        raise e
    
def increment_organization_questions_used(organization_id: str, amount=1) -> OrganizationsORM:
    """Update an organization's quota"""
    try:
        with Session() as session:
            organization = session.query(OrganizationsORM).filter(OrganizationsORM.id == organization_id).first()
            organization.questions_used += amount
            session.commit()
            session.refresh(organization)
            session.expunge(organization)
            return organization
    except Exception as e:
        raise e


def get_organizations_for_quota_reset(target_date: date = None) -> List[OrganizationsORM]:
    """Get organizations that need quota reset for a specific date"""
    try:
        with Session() as session:
            if target_date is None:
                target_date = date.today()
            
            orgs = session.query(OrganizationsORM).filter(
                OrganizationsORM.quota_reset_date == target_date
            ).all()
            for org in orgs:
                session.expunge(org)
            return orgs
    except Exception as e:
        raise e


def reset_organization_quota(organization_id: str, new_quota_reset_date: date) -> OrganizationsORM:
    """Reset an organization's quota and update reset date"""
    try:
        with Session() as session:
            organization = session.query(OrganizationsORM).filter(
                OrganizationsORM.id == organization_id
            ).first()
            
            if organization:
                organization.questions_used = 0
                organization.quota_reset_date = new_quota_reset_date
                session.commit()
                session.refresh(organization)
                session.expunge(organization)
            
            return organization
    except Exception as e:
        raise e


def get_organization_by_id_for_quota(organization_id: str) -> OrganizationsORM:
    """Get organization by ID for quota operations"""
    try:
        with Session() as session:
            org = session.query(OrganizationsORM).filter(
                OrganizationsORM.id == organization_id
            ).first()
            if org:
                session.expunge(org)
            return org
    except Exception as e:
        raise e