from django.db import models

# Create your models here.
from django.db import models

class Ticker(models.Model):
    # Identification
    symbol = models.CharField(max_length=20)
    short_name = models.CharField(max_length=100, null=True, blank=True)
    long_name = models.CharField(max_length=255, null=True, blank=True)
    display_name = models.CharField(max_length=255, null=True, blank=True)

    # Market Info
    market = models.CharField(max_length=50, null=True, blank=True)
    quote_type = models.CharField(max_length=50, null=True, blank=True)
    exchange = models.CharField(max_length=50, null=True, blank=True)
    full_exchange_name = models.CharField(max_length=100, null=True, blank=True)
    financial_currency = models.CharField(max_length=10, null=True, blank=True)

    # Pricing
    regular_market_price = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    regular_market_change = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    regular_market_change_percent = models.FloatField(null=True, blank=True)
    regular_market_open = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    regular_market_day_high = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    regular_market_day_low = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    regular_market_previous_close = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    regular_market_volume = models.BigIntegerField(null=True, blank=True)

    pre_market_price = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    pre_market_change = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    pre_market_change_percent = models.FloatField(null=True, blank=True)

    # Averages
    fifty_day_average = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    two_hundred_day_average = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    # Dividend
    dividend_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    dividend_yield = models.FloatField(null=True, blank=True)
    trailing_annual_dividend_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    trailing_annual_dividend_yield = models.FloatField(null=True, blank=True)

    # Earnings
    eps_trailing_twelve_months = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    eps_forward = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    eps_current_year = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    forward_pe = models.FloatField(null=True, blank=True)
    trailing_pe = models.FloatField(null=True, blank=True)
    price_eps_current_year = models.FloatField(null=True, blank=True)

    # Other Metrics
    market_cap = models.BigIntegerField(null=True, blank=True)
    shares_outstanding = models.BigIntegerField(null=True, blank=True)
    book_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    price_to_book = models.FloatField(null=True, blank=True)
    average_analyst_rating = models.CharField(max_length=50, null=True, blank=True)

    # 52-week range
    fifty_two_week_range = models.CharField(max_length=50, null=True, blank=True)
    fifty_two_week_high = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    fifty_two_week_low = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    fifty_two_week_high_change = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    fifty_two_week_low_change = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    fifty_two_week_change_percent = models.FloatField(null=True, blank=True)

    # Flags & Meta
    market_state = models.CharField(max_length=20, null=True, blank=True)
    crypto_tradeable = models.BooleanField(default=False)
    tradeable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["symbol", "created_at"]),
        ]

    def __str__(self):
        return f"{self.symbol} @ {self.regular_market_price}"
