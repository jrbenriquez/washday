from datetime import time

import pytest
from core.models import Shop, Branch, Settings, JobStage
from core.tenancy import shop_context
from catalog.models import Service, PieceItem, PieceVariant, AddOn, Fee
from people.models import Staff


@pytest.fixture
def setup_shop(db):
    shop = Shop.objects.create(name="TEST ONLY Ivan & Ivy Laundry", code="TEST")
    with shop_context(shop):
        branch = Branch.objects.create(
            shop=shop, name="TEST branch", number=1, code="TEST",
            opening_time=time(0), closing_time=time(0),
        )
        Settings.objects.create(shop=shop, min_kg="3.0", kg_per_load="7.0")
        for i, name in enumerate(["Received", "Washing", "Drying", "Folding", "Ready"]):
            JobStage.objects.create(
                shop=shop,
                name=name,
                sort_order=i,
                is_first=i == 0,
                is_last=i == 4,
                ask_for_machine=i in [1, 2],
            )
        service = Service.objects.create(
            shop=shop, name="TEST service", mode="kg", price="35.05"
        )
        load = Service.objects.create(
            shop=shop, name="TEST load", mode="load", price="150.00"
        )
        item = PieceItem.objects.create(shop=shop, name="TEST comforter")
        variant = PieceVariant.objects.create(
            shop=shop, piece_item=item, label="Queen", price="180.00"
        )
        addon = AddOn.objects.create(shop=shop, name="TEST addon", price="20.00")
        fee = Fee.objects.create(
            shop=shop, name="Rush", note="Same day", amount="50.00"
        )
        staff = Staff.objects.create(
            shop=shop, branch=branch, name="TEST staff", pin_hash="!"
        )
        yield dict(
            shop=shop,
            branch=branch,
            service=service,
            load=load,
            variant=variant,
            addon=addon,
            fee=fee,
            staff=staff,
        )


@pytest.fixture
def scoped_client(setup_shop, client, settings):
    settings.DEV_BRANCH_ID = str(setup_shop["branch"].id)
    settings.DEV_STAFF_ID = str(setup_shop["staff"].id)
    settings.DEBUG = True
    settings.ENABLE_DEV_BRANCH_SCOPE = True
    return client
