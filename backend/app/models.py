from __future__ import annotations
from typing import Optional, List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey, func, Index

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"

    org_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, default="")
    city: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    country: Mapped[Optional[str]] = mapped_column(String)
    postal_code: Mapped[Optional[str]] = mapped_column(String)
    latitude: Mapped[Optional[Float]]
    longitude: Mapped[Optional[Float]]
    website: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    phone: Mapped[Optional[str]] = mapped_column(String)

    animals: Mapped[List["Animal"]] = relationship(
        back_populates="org",
        cascade="all, delete-orphan"
    )

class Animal(Base):
    __tablename__ = "animals"

    animal_id: Mapped[int] = mapped_column(primary_key=True)  # Petfinder numeric id
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.org_id"), index=True)

    description: Mapped[Optional[str]] #TODO: sentiment analysis?

    # commonly provided descriptors
    type: Mapped[Optional[str]] = mapped_column(String, index=True)
    species: Mapped[Optional[str]] = mapped_column(String, index=True)
    breed_known: Mapped[Optional[bool]] = mapped_column(Boolean)
    breed_mixed: Mapped[Optional[bool]] = mapped_column(Boolean)
    breed_primary: Mapped[Optional[str]] = mapped_column(String)
    breed_secondary: Mapped[Optional[str]] = mapped_column(String)
    age: Mapped[Optional[str]] = mapped_column(String, index=True)  # baby/young/adult/senior
    size: Mapped[Optional[str]] = mapped_column(String)
    gender: Mapped[Optional[str]] = mapped_column(String)

    # less commonly provided descriptors
    special_needs: Mapped[bool] = mapped_column(Boolean, default=False)
    spayed_neutered: Mapped[Optional[bool]] = mapped_column(Boolean)
    house_trained: Mapped[Optional[bool]] = mapped_column(Boolean)
    declawed: Mapped[Optional[bool]] = mapped_column(Boolean)
    shots_current: Mapped[Optional[bool]] = mapped_column(Boolean)
    good_with_children: Mapped[Optional[bool]] = mapped_column(Boolean)
    good_with_dogs: Mapped[Optional[bool]] = mapped_column(Boolean)
    good_with_cats: Mapped[Optional[bool]] = mapped_column(Boolean)

    photo_count: Mapped[int] = mapped_column(Integer, default=0)
    bio_len: Mapped[int] = mapped_column(Integer, default=0)

    first_adoptable_ts: Mapped[Optional[DateTime]]
    first_adopted_ts: Mapped[Optional[DateTime]]

    org: Mapped["Organization"] = relationship(back_populates="animals")
    statuses: Mapped[List["AnimalStatusHistory"]] = relationship(
        back_populates="animal",
        cascade="all, delete-orphan"
    )

Index("ix_animals_type_age", Animal.type, Animal.age)

class AnimalStatusHistory(Base):
    __tablename__ = "animal_status_history"

    # surrogate primary key for history rows
    id: Mapped[int] = mapped_column(primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.animal_id"), index=True)

    status: Mapped[str] = mapped_column(String, index=True)    # adoptable/adopted/found
    status_ts: Mapped[DateTime] = mapped_column(DateTime(timezone=True))

    seen_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    row_hash: Mapped[str] = mapped_column(String, index=True)  # idempotency

    animal: Mapped["Animal"] = relationship(back_populates="statuses")


# TODO: maybe future index (add in later migration if needed):
# Index("ix_status_by_org_time", AnimalStatusHistory.animal_id, AnimalStatusHistory.status_ts)
