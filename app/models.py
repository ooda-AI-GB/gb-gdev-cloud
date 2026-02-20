from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, Date, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class CloudAccount(Base):
    __tablename__ = "cloud_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    provider = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    account_id = Column(String(200), nullable=False)
    credentials_ref = Column(Text, nullable=True)
    region = Column(String(50), nullable=True)
    status = Column(String(20), default="connected")
    last_polled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    resources = relationship("CloudResource", back_populates="account")
    cost_records = relationship("CostRecord", back_populates="account")
    waste_alerts = relationship("WasteAlert", back_populates="account")
    budgets = relationship("Budget", back_populates="account")
    optimization_recommendations = relationship("OptimizationRecommendation", back_populates="account")
    ai_insights = relationship("AIInsight", back_populates="account")


class CloudResource(Base):
    __tablename__ = "cloud_resources"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("cloud_accounts.id"), nullable=False)
    resource_id = Column(String(200), nullable=False)
    resource_type = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    region = Column(String(50), nullable=True)
    status = Column(String(20), default="unknown")
    provider_status = Column(String(100), nullable=True)
    config = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("CloudAccount", back_populates="resources")
    cost_records = relationship("CostRecord", back_populates="resource")
    utilization_snapshots = relationship("UtilizationSnapshot", back_populates="resource")
    waste_alerts = relationship("WasteAlert", back_populates="resource")
    optimization_recommendations = relationship("OptimizationRecommendation", back_populates="resource")


class CostRecord(Base):
    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("cloud_accounts.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=True)
    date = Column(Date, nullable=False)
    service = Column(String(100), nullable=False)
    sku = Column(String(200), nullable=True)
    amount = Column(Float, default=0)
    currency = Column(String(10), default="USD")
    usage_quantity = Column(Float, nullable=True)
    usage_unit = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("CloudAccount", back_populates="cost_records")
    resource = relationship("CloudResource", back_populates="cost_records")


class UtilizationSnapshot(Base):
    __tablename__ = "utilization_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=False)
    snapshot_time = Column(DateTime(timezone=True), nullable=False)
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)
    network_in_bytes = Column(Integer, nullable=True)
    network_out_bytes = Column(Integer, nullable=True)
    request_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resource = relationship("CloudResource", back_populates="utilization_snapshots")


class WasteAlert(Base):
    __tablename__ = "waste_alerts"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("cloud_accounts.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    estimated_monthly_waste = Column(Float, default=0)
    status = Column(String(20), default="open")
    recommendation = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("CloudAccount", back_populates="waste_alerts")
    resource = relationship("CloudResource", back_populates="waste_alerts")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    account_id = Column(Integer, ForeignKey("cloud_accounts.id"), nullable=True)
    name = Column(String(100), nullable=False)
    monthly_limit = Column(Float, nullable=False)
    alert_threshold_percent = Column(Float, default=80.0)
    current_spend = Column(Float, default=0)
    period_start = Column(Date, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("CloudAccount", back_populates="budgets")


class OptimizationRecommendation(Base):
    __tablename__ = "optimization_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("cloud_accounts.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=True)
    category = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    estimated_monthly_savings = Column(Float, default=0)
    effort = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")
    model_used = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("CloudAccount", back_populates="optimization_recommendations")
    resource = relationship("CloudResource", back_populates="optimization_recommendations")


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("cloud_accounts.id"), nullable=True)
    insight_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="info")
    data_context = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("CloudAccount", back_populates="ai_insights")
