"""YearExtraFlag model tracks if the 'beyond-limit prompt' has been shown this year."""

from sqlalchemy import Column, Integer, Boolean, text

from src.database import Base


class YearExtraFlag(Base):
    __tablename__ = "year_extra_flag"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, unique=True)
    asked = Column(Boolean, nullable=False, server_default=text("FALSE"))

    def __repr__(self) -> str:
        return f"<YearExtraFlag(year={self.year}, asked={self.asked})>"
