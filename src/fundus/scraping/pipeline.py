from typing import Iterator, List, Literal, Optional, Set, Tuple, Type, Union

import more_itertools

from fundus.publishers.base_objects import PublisherEnum
from fundus.scraping.article import Article
from fundus.scraping.filter import ExtractionFilter
from fundus.scraping.html import URLSource
from fundus.scraping.scraper import Scraper
from fundus.utils.validation import listify


class Pipeline:
    def __init__(self, *scrapers: Scraper):
        self.scrapers: Tuple[Scraper, ...] = scrapers

    def run(
        self,
        error_handling: Literal["suppress", "catch", "raise"],
        max_articles: Optional[int] = None,
        extraction_filter: Optional[ExtractionFilter] = None,
        batch_size: int = 10,
    ) -> Iterator[Article]:
        scrape_map = map(
            lambda x: x.scrape(
                error_handling=error_handling, batch_size=batch_size, extraction_filter=extraction_filter
            ),
            self.scrapers,
        )
        robin = more_itertools.interleave_longest(*tuple(scrape_map))

        if max_articles:
            while max_articles:
                try:
                    yield next(robin)
                except StopIteration:
                    pass
                max_articles -= 1
        else:
            yield from robin


class Crawler:
    def __init__(self, *publishers: Union[PublisherEnum, Type[PublisherEnum]]):
        if not publishers:
            raise ValueError("param <publishers> of <Crawler.__init__> has to be non empty")
        nested_publisher = [listify(publisher) for publisher in publishers]
        self.publishers: Set[PublisherEnum] = set(more_itertools.flatten(nested_publisher))

    def crawl(
        self,
        max_articles: Optional[int] = None,
        restrict_sources_to: Optional[List[Type[URLSource]]] = None,
        error_handling: Literal["suppress", "catch", "raise"] = "suppress",
        only_complete: Union[bool, ExtractionFilter] = True,
        batch_size: int = 10,
    ) -> Iterator[Article]:
        extraction_filter: Optional[ExtractionFilter]
        if isinstance(only_complete, bool):
            extraction_filter = (
                None
                if only_complete is False
                else lambda extracted: all(
                    bool(v) if not isinstance(v, Exception) else False for k, v in extracted.items()
                )
            )
        else:
            extraction_filter = only_complete

        scrapers: List[Scraper] = []
        for spec in self.publishers:
            if restrict_sources_to:
                sources = more_itertools.flatten(
                    spec.source_mapping[source_type.__name__] for source_type in restrict_sources_to
                )
            else:
                sources = more_itertools.flatten(spec.source_mapping.values())

            if sources:
                scrapers.append(
                    Scraper(
                        *sources,
                        parser=spec.parser,
                    )
                )

        if scrapers:
            pipeline = Pipeline(*scrapers)
            return pipeline.run(
                error_handling=error_handling,
                max_articles=max_articles,
                batch_size=batch_size,
                extraction_filter=extraction_filter,
            )
        else:
            return iter(())
